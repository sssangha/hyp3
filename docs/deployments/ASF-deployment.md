# Deploying HyP3 to ASF

This guide walks through deploying HyP3 into an ASF managed AWS commercial cloud account.
It should work for any new ASF account.

## 1. Set up a CloudFormation templates bucket

A new account will not have a bucket for storing AWS CloudFormation templates,
which is needed to deploy a CloudFormation stack. AWS will automatically make a
suitable bucket if you try and create a new CloudFormation Stack in the AWS Console:
* navigating to the CloudFormation service in the region you are going to deploy to
* Click the orange "Create stack" button 
* On the create stack screen
  * For "Prepare template" make select "Template is ready"
  * For "Template source" select "Upload a template file"
  * Choose any JSON or YAML formatted file from your computer to upload
  * Once the file is uploaded, you should see an S3 URL on the bottom indicating the
    bucket the template file was uploaded. This is your newly created CloudFormation
    templates bucket and should be named something like `cf-templates-<HASH>-<region>`
  * Click "Cancel" to exit the CloudFormation stack creation now that we have a
    templates bucket


## 2.  Prepare for deployment

In order to integrate an ASF deployment we'll need:
* Set the account-wide API Gateway logging permissions
* A deployment role with the necessary permissions to deploy HyP3
* A "service user" so that we can generate long-term AWS access keys and
  integrate the deployment into our CI/CD pipelines

These can be done by deploying the `hyp3-ci` stack. From the repository root, run:

```shell
aws cloudformation deploy \
    --stack-name hyp3-ci \
    --template-file docs/deployments/ASF-deployment-ci-cf.yml \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides TemplateBucketName=<template-bucket>
```

***Note:** This stack should only be deployed once per AWS account. This stack also
assumes you are only deploying into a single AWS Region If you are deploying into
multiple regions in the same AWS account, you'll need to adjust the IAM permissions
that are limited to a single region.*

## 3. Deploy HyP3 to AWS

Once the `github-actions` IAM user has been created, you can create a set of AWS
Access Keys for that user, which can be used to deploy HyP3 via CI/CD tooling. 
You may want to deploy HyP3 manually with the `github-actions` IAM user access keys
to verify that the `github-actions` user has sufficient deployment permissions.

To deploy HyP3 manually, using either the `github-actions` access keys or your own,
run these commands from the repository root, replacing any `<*>` with appropriate
values, and adding any other needed parameter overrides for the deployment:

```shell
export AWS_ACCESS_KEY_ID=<service-user-access-key-id>
export AWS_SECRET_ACCESS_KEY=<service-user-secret-access-key>
export AWS_REGION=<deployment-region>

make files=<supported-job-spec-files> security_environment=ASF build

aws cloudformation package \
    --template-file apps/main-cf.yml \
    --s3-bucket <template-bucket> \
    --output-template-file packaged.yml

aws cloudformation deploy \
    --stack-name <stack-name> \
    --template-file packaged.yml \
    --role-arn <cloudformation-deployment-role-arn> \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        VpcId=<vpc-ids> \
        SubnetIds=<subnet-ids> \
        EDLUsername=<earthdata-login-username> \
        EDLPassword=<earthdata-login-password> \
        DomainName=<domain-name> \
        CertificateArn=<certificate-arn>
```
