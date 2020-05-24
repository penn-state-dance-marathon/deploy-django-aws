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
  python aws_cicd.py <application> <environment>

Example:
  python aws_cicd.py dash dev
"""
import argparse
import boto3


# Argument parser pulls in the application and environment
parser = argparse.ArgumentParser()
parser.add_argument(
    'application',
    help='the AWS name of your application (e.g. dash)')
parser.add_argument(
    'environment',
    help='which environment your are deploying (e.g. dev, prod)')
args = parser.parse_args()


def main():
    """Run the AWS commands"""
    # Prepare the naming convention of applications on AWS
    cluster_name = '{}-{}'.format(args.application, args.environment)

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
    task_resp = ecs.list_task_definitions(
        familyPrefix='{}-migrate'.format(cluster_name), sort='DESC')
    try:
        latest_migration_task = task_resp['taskDefinitionArns'][0]
    except IndexError:
        print('ERROR: There is no task definition following the "{}-migrate" '
              ' naming convention.'.format(cluster_name))
        return

    ecs.run_task(cluster=cluster_name,
                 launchType='FARGATE',
                 taskDefinition=latest_migration_task,
                 networkConfiguration={
                     'awsvpcConfiguration': {
                         'subnets': subnets,
                         'securityGroups': security_groups,
                         'assignPublicIp': 'ENABLED'
                     }
                 })

    # Update each service in cluster, forcing new deployment
    services_resp = ecs.list_services(cluster=cluster_name)
    for service in services_resp['serviceArns']:
        ecs.update_service(
            cluster=cluster_name,
            service=service,
            forceNewDeployment=True)


if __name__ == "__main__":
    main()
