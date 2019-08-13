import os
import boto3

# AWS account info
AWS_ACCOUNT_NUMBER = os.environ.get('AWS_ACCOUNT_NUMBER', '')
if not AWS_ACCOUNT_NUMBER:
    AWS_LAMBDA_FUNCTION_NAME = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', '')
    # I'm a lambda
    if AWS_LAMBDA_FUNCTION_NAME:
        try:
            res = boto3.client('lambda').get_function(FunctionName=AWS_LAMBDA_FUNCTION_NAME)
            AWS_ACCOUNT_NUMBER = res['Configuration']['FunctionArn'].split(':')[4]
        except Exception as e:
            raise Exception("Cannot find AWS_ACCOUNT_NUMBER: %s" % e)
    # I'm a user
    elif not AWS_ACCOUNT_NUMBER:
        try:
            AWS_ACCOUNT_NUMBER = boto3.resource('iam').CurrentUser().arn.split(':')[4]
        except Exception as e:
            raise Exception("Cannot find AWS_ACCOUNT_NUMBER: %s" % e)

AWS_REGION = os.environ.get('TIBANNA_AWS_REGION', '')
if not AWS_REGION:
    # I'm a lambda
    AWS_REGION = os.environ.get('AWS_REGION', '')  # reserved variable in lambda
    # I'm a user
    if not AWS_REGION:
        try:
            AWS_REGION = boto3.session.Session().region_name  # for a user
        except Exception as e:
            raise Exception("Cannot find AWS_REGION: %s" % e)


# Tibanna AMI info
AMI_ID_CWL_V1 = 'ami-0f06a8358d41c4b9c'
AMI_ID_CWL_DRAFT3 = 'ami-0f06a8358d41c4b9c'
AMI_ID_WDL = 'ami-0f06a8358d41c4b9c'
AMI_ID_SHELL = 'ami-0f06a8358d41c4b9c'
AMI_ID_SNAKEMAKE = 'ami-0f06a8358d41c4b9c'

# Tibanna repo from which awsf scripts are pulled
TIBANNA_REPO_NAME = os.environ.get('TIBANNA_REPO_NAME', '4dn-dcic/tibanna')
TIBANNA_REPO_BRANCH = os.environ.get('TIBANNA_REPO_BRANCH', 'master')

# Tibanna roles
AWS_S3_ROLE_NAME = os.environ.get('AWS_S3_ROLE_NAME', 'S3_access')
S3_ACCESS_ARN = 'arn:aws:iam::' + AWS_ACCOUNT_NUMBER + ':instance-profile/' + AWS_S3_ROLE_NAME

# Profile keys (optional) to use on AWSEM EC2
TIBANNA_PROFILE_ACCESS_KEY = os.environ.get('TIBANNA_PROFILE_ACCESS_KEY', '')
TIBANNA_PROFILE_SECRET_KEY = os.environ.get('TIBANNA_PROFILE_SECRET_KEY', '')

# default step function name
TIBANNA_DEFAULT_STEP_FUNCTION_NAME = os.environ.get('TIBANNA_DEFAULT_STEP_FUNCTION_NAME', 'tibanna_unicorn')

# dynamo table (optional) for fast searching
DYNAMODB_TABLE = 'tibanna-master'

# field name reserved for Tibanna setting
_tibanna = '_tibanna'

# step function and execution ARN generators
BASE_ARN = 'arn:aws:states:' + AWS_REGION + ':' + AWS_ACCOUNT_NUMBER + ':%s:%s'
BASE_EXEC_ARN = 'arn:aws:states:' + AWS_REGION + ':' + AWS_ACCOUNT_NUMBER + ':execution:%s:%s'


def STEP_FUNCTION_ARN(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    return BASE_ARN % ('stateMachine', sfn)


def EXECUTION_ARN(exec_name, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    return BASE_EXEC_ARN % (sfn, exec_name)
