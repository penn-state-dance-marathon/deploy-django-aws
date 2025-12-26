"""
This script is used for the CI/CD workflow of Django-based sites running
on AWS. Make sure you have the AWS boto3 Python SDK installed and your
AWS IAM credentials configured.

The overall process is as follows:
  1. Collect the proper subnets and security groups to launch ECS tasks
  2. Run the ECS Django migrations task to update the db and static files
  3. Restart all ECS services so they use the most updated Docker image

A few assumptions are made in this script due to the nature of AWS:
 - You are running your ECS tasks in the "default" VPC
 - You have a security group named "ecs" that gives all proper firewall
   rules (database, Redis, etc)
 - Your ECS cluster is named <application>-<environment> (e.g. dash-dev)
 - You have a task definition that runs Django migrations with the name of
   <application>-<environment>-migrate

Usage:
  python python_cicd.py <application> <environment>

Example:
  python python_cicd.py dash dev
"""
import argparse
import boto3
import sys
import time

from botocore.exceptions import ClientError
from datetime import datetime


# Argument parser pulls in the application and environment
parser = argparse.ArgumentParser()
parser.add_argument(
    'application',
    help='the AWS name of your application (e.g. dash)')
parser.add_argument(
    'environment',
    help='which environment your are deploying (e.g. dev, prod)')
parser.add_argument(
    '-g', '--group',
    help='the name of the CloudWatch log group where logs are stored.')
parser.add_argument(
    '-p', '--prefix',
    help='the characters that precede the task ID in the CloudWatch log stream name')
args = parser.parse_args()


def main():
    """Run the AWS commands"""
    # Prepare the naming convention of applications on AWS
    cluster_name = '{}-{}'.format(args.application, args.environment)

    log_group_name = '/ecs/{}/{}'.format(args.application, args.environment)
    if args.group is not None:
        log_group_name = args.group

    log_stream_prefix = 'ecs-{}-{}/{}-{}'.format(
        args.application,
        args.environment,
        args.application,
        args.environment
    )
    if args.prefix is not None:
        log_stream_prefix = args.prefix

    # Get subnets and security groups to run migration task under
    ec2 = boto3.client('ec2')
    vpc_resp = ec2.describe_vpcs(
        Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    try:
        vpc_id = vpc_resp['Vpcs'][0]['VpcId']
    except IndexError:
        print('ERROR: The default VPC does not exist. '
              'Either something very bad has happened or '
              'this script needs to be updated.')
        return

    vpc = boto3.resource('ec2').Vpc(vpc_id)
    subnets = [subnet.id for subnet in vpc.subnets.all()]
    security_groups = [
        sg.id for sg in vpc.security_groups.filter(GroupNames=['ecs'])
     ]

    # Find the migration task definition and run it under sufficient security
    # groups and subnets
    ecs = boto3.client('ecs')
    logs = boto3.client('logs')
    task_resp = ecs.list_task_definitions(
        familyPrefix='{}-migrate'.format(cluster_name), sort='DESC')
    try:
        latest_migration_task = task_resp['taskDefinitionArns'][0]
        # Launch migration task
        response = ecs.run_task(cluster=cluster_name,
                                launchType='FARGATE',
                                taskDefinition=latest_migration_task,
                                networkConfiguration={
                                    'awsvpcConfiguration': {
                                        'subnets': subnets,
                                        'securityGroups': security_groups,
                                        'assignPublicIp': 'ENABLED'
                                    }
                                })
        print('Successfully started migrate task. Waiting for it to complete...')

        # Wait until the task enters tasks_stopped
        # Inspired by https://stackoverflow.com/questions/33701140/using-aws-ecs-with-boto3
        task_arn = response['tasks'][0]['taskArn']
        waiter = ecs.get_waiter('tasks_stopped')
        waiter.wait(cluster=cluster_name, tasks=[task_arn])

        # Get log events
        # ECS task ARN format: arn:aws:ecs:region:account:task/cluster-name/task-id
        # Extract task ID (the part after the last '/')
        task_id = task_arn.split('/')[-1]
        log_stream_name = '{}/{}'.format(log_stream_prefix, task_id)

        # Try to get log events with error handling
        # CloudWatch logs may not be immediately available after task stops
        max_retries = 5
        retry_delay = 2  # seconds
        migration_logs = []
        
        for attempt in range(max_retries):
            try:
                response = logs.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=log_stream_name,
                    startFromHead=True
                )
                migration_logs = response['events']
                break
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'ResourceNotFoundException':
                    if attempt < max_retries - 1:
                        print('Log stream not found yet, waiting {} seconds before retry...'.format(retry_delay))
                        time.sleep(retry_delay)
                    else:
                        print('Warning: Could not retrieve logs from log stream "{}". '
                              'The log stream may not exist or logs may not be configured.'.format(log_stream_name))
                        print('Attempting to continue without logs...')
                else:
                    # Re-raise if it's a different error
                    raise
        
        for event in migration_logs:
            message = event['message']
            print(message)

        # Get the container exit code - if not zero, houston we have a problem
        response = ecs.describe_tasks(
            cluster=cluster_name,
            tasks=[task_arn]
        )
        task_exit_code = response['tasks'][0]['containers'][0]['exitCode']
        if task_exit_code != 0:
            print('A migration error has occurred: please see the above logs.', file=sys.stderr)
            sys.exit(1)
        print('Migrate task complete.')
    except IndexError:
        print('There is no task definition following the "{}-migrate"'
              ' naming convention. Skipping...'.format(cluster_name))

    # Update each service in cluster, forcing new deployment
    services_resp = ecs.list_services(cluster=cluster_name)
    for service in services_resp['serviceArns']:
        # Get the task definition associated with the service so we can
        # use the latest one
        service_info = ecs.describe_services(cluster=cluster_name,
                                             services=[service])
        service_task = service_info['services'][0]['taskDefinition']
        task_info = ecs.describe_task_definition(taskDefinition=service_task)
        task_family = task_info['taskDefinition']['family']
        ecs.update_service(
            cluster=cluster_name,
            service=service,
            taskDefinition=task_family,
            forceNewDeployment=True)

    # Invalidate the Cloudfront cache as well
    app_tag = {'Key': 'Application', 'Value': args.application}
    env_tag = {'Key': 'Environment', 'Value': args.environment}
    cloudfront = boto3.client('cloudfront')
    dists = cloudfront.list_distributions()['DistributionList']['Items']
    for dist in dists:
        tags = cloudfront.list_tags_for_resource(Resource=dist['ARN'])
        tags = tags['Tags']['Items']
        caller_reference = datetime.now().strftime('%Y%m%d%H%M%S%f')
        if app_tag in tags and env_tag in tags:
            cloudfront.create_invalidation(DistributionId=dist['Id'],
                                           InvalidationBatch={
                                               'Paths': {
                                                   'Quantity': 1,
                                                   'Items': ['/*']
                                               },
                                               'CallerReference': caller_reference})


if __name__ == "__main__":
    main()
