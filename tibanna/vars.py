import os
import boto3
import sys
from datetime import datetime
from dateutil.tz import tzutc


if boto3.session.Session().get_credentials() is None:
    print('Please provide AWS credentials.')
    sys.exit(-1)


# AWS account info
AWS_ACCOUNT_NUMBER = os.environ.get('AWS_ACCOUNT_NUMBER', '')
if not AWS_ACCOUNT_NUMBER:
    try:
        AWS_ACCOUNT_NUMBER = boto3.client('sts').get_caller_identity().get('Account')
    except Exception as e:
        raise Exception("Cannot obtain AWS account number. Please provide AWS credentials")

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
AMI_PER_REGION = {
    # new AMI based on ubuntu 20.04 works with awsf3 and it's available only for us-east-1.
    'us-east-1': 'ami-02ae7b71d31f3a24e',
    'ap-south-1' : 'ami-09d95d9217d0cf385',
    'ap-northeast-2' : 'ami-0c41548ca349c7a24',
    'ap-southeast-1' : 'ami-05ed988e6e239f8ab',
    'ap-southeast-2' : 'ami-08015a75aa06d5169',
    'ap-northeast-1' : 'ami-0ca2f82fea1712d9c',
    'ca-central-1': 'ami-0db70f7b86ac96a83',
    'eu-central-1': 'ami-04e369eb9ff2f4f2d',
    'eu-west-1': 'ami-02de1cc972d19b5f0',
    'eu-west-2': 'ami-092454e8dfc2d7fa6',
    'eu-west-3': 'ami-02f01bb8e27345b00',
    'eu-north-1': 'ami-06cff15ceaadf54ca',
    'sa-east-1': 'ami-06f63076e5a4fa510',
    'us-east-2': 'ami-0691eb4caeced8412',
    'us-west-1': 'ami-009aab2c590a01210',
    'us-west-2': 'ami-05bcbe2628605a628'
}
AMI_ID = AMI_PER_REGION.get(AWS_REGION, '')
if not AMI_ID:
    raise Exception("AMI for region %s is not supported" % AWS_REGION)

# Tibanna repo from which awsf scripts are pulled
TIBANNA_REPO_NAME = os.environ.get('TIBANNA_REPO_NAME', '4dn-dcic/tibanna')
TIBANNA_REPO_BRANCH = os.environ.get('TIBANNA_REPO_BRANCH', 'master')
if AWS_REGION == 'us-east-1':
    TIBANNA_AWSF_DIR = 'awsf3'
else:
    TIBANNA_AWSF_DIR = 'awsf'

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
DYNAMODB_KEYNAME = 'Job Id'

# field name reserved for Tibanna setting
_tibanna = '_tibanna'

# Awsem time stamp format
AWSEM_TIME_STAMP_FORMAT = '%Y%m%d-%H:%M:%S-UTC'


def PARSE_AWSEM_TIME(t_str):
  t = datetime.strptime(t_str, AWSEM_TIME_STAMP_FORMAT)
  return t.replace(tzinfo=tzutc())


# EBS mount path for cloudwatch metric collection
EBS_MOUNT_POINT = '/mnt/data1'


# Default root EBS size
DEFAULT_ROOT_EBS_SIZE = 8


SFN_TYPE = 'unicorn'
LAMBDA_TYPE = ''
RUN_TASK_LAMBDA_NAME = 'run_task_awsem'
CHECK_TASK_LAMBDA_NAME = 'check_task_awsem'


# step function and execution ARN generators
BASE_ARN = 'arn:aws:states:' + AWS_REGION + ':' + AWS_ACCOUNT_NUMBER + ':%s:%s'
BASE_EXEC_ARN = 'arn:aws:states:' + AWS_REGION + ':' + AWS_ACCOUNT_NUMBER + ':execution:%s:%s'
BASE_METRICS_URL = 'https://%s.s3.amazonaws.com/%s.metrics/metrics.html'

def STEP_FUNCTION_ARN(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    return BASE_ARN % ('stateMachine', sfn)


def EXECUTION_ARN(exec_name, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    return BASE_EXEC_ARN % (sfn, exec_name)


def METRICS_URL(log_bucket, job_id):
    return BASE_METRICS_URL % (log_bucket, job_id)
