# Django Deploy AWS

This action forces a rolling restart of tagged AWS resources to initiate a rolling Django deployment. The action grabs and restarts all resources that match the provided tag names.

## Inputs

### `application`

**Required.** The tagged application name in AWS to redeploy.

### `environment`

**Required.** The tagged environment name in AWS to redeploy.

### `logGroupName`

Optional. The name of the log group that stores logs for this application's migration task.

Default: `/ecs/${application}/${environment}`

### `logStreamPrefix`

Optional. The constant portion of the log stream name that prefixes the ECS Task ID.

Default: `ecs-${application}-${environment}/${application}-${environment}

## Example usage

<pre>
uses: actions/django-deploy-aws@v1
with:
  application: 'dash'
  environment: 'prod'
</pre>
