# Django Deploy AWS

This action forces a rolling restart of tagged AWS resources to initiate a rolling Django deployment. The action grabs and restarts all resources that match the provided tag names.

## Inputs

### `application`

**Required** The tagged application name in AWS to redeploy.

### `environment`

**Required** The tagged environment name in AWS to redeploy.

## Example usage

<pre>
uses: actions/django-deploy-aws@v1
with:
  application: 'dash'
  environment: 'prod'
</pre>
