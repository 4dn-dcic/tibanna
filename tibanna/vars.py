import os
import boto3
import sys
from datetime import datetime
from dateutil.tz import tzutc
from ._version import __version__
from . import create_logger


logger = create_logger(__name__)


if boto3.session.Session().get_credentials() is None:
    logger.info('Please provide AWS credentials.')
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
# Override this mapping to use a custom AMI scheme
AMI_PER_REGION = {
    'x86': {
        'us-east-1': 'ami-06e2266f85063aabc',  # latest as of Oct 25 2021
        'us-east-2': 'ami-03a4e3e84b6a1813d',
        'us-west-1': 'ami-0c5e8147be760a354',
        'us-west-2': 'ami-068589fed9c8d5950',
        'ap-south-1': 'ami-05ef59bc4f359c93b',
        'ap-northeast-2': 'ami-0d8618a76aece8a8e',
        'ap-southeast-1': 'ami-0c22dc3b05714bda1',
        'ap-southeast-2': 'ami-03dc109bbf412aac5',
        'ap-northeast-1': 'ami-0f4c520515c41ff46',
        'ca-central-1': 'ami-01af127710fadfe74',
        'eu-central-1': 'ami-0887bcb1c901c1769',
        'eu-west-1': 'ami-08db59692e4371ea6',
        'eu-west-2': 'ami-036d3ce7a21e07012',
        'eu-west-3': 'ami-0cad0ec4160a6b940',
        'eu-north-1': 'ami-00a6f0f9fee951aa0',
        'sa-east-1': 'ami-0b2164f9680f97099',
        'me-south-1': 'ami-03479b7a590f97945',
        'af-south-1': 'ami-080baa4ec59c456aa',
        'ap-east-1': 'ami-0a9056eb817bc3928',
        'eu-south-1': 'ami-0a72279e56849415e'
    },
    'Arm': {
        'us-east-1': 'ami-0f3e90ad8e76c7a32', # latest as of Nov 23 2022
        'us-east-2': 'ami-03359d89f311a015e', 
        'us-west-1': 'ami-00ffd20b39dbfb6ea', 
        'us-west-2': 'ami-08ab3015c1bc36d24', 
        'ap-south-1': 'ami-01af9ec07fed38a38', 
        'ap-northeast-2': 'ami-0ee2af459355dd917', 
        'ap-southeast-1': 'ami-0d74dc5af4bf74ea8', 
        'ap-southeast-2': 'ami-08ab7201c83209fe8', 
        'ap-northeast-1': 'ami-07227003bfa0565e3', 
        'ca-central-1': 'ami-0cbf87c80362a058e', 
        'eu-central-1': 'ami-09cfa59f75e88ad54', 
        'eu-west-1': 'ami-0804bdeafd8af01f8', 
        'eu-west-2': 'ami-0db05a333dc02c1c8', 
        'eu-west-3': 'ami-0ceab436f882fe36a', 
        'eu-north-1': 'ami-04ba962c974ddd374', 
        'sa-east-1': 'ami-0fc9a9dec0f3df318', 
        'me-south-1': 'ami-0211bc858eb163594', 
        'af-south-1': 'ami-0d6a4af087f83899d', 
        'ap-east-1': 'ami-0d375f2ce688d16b9', 
        'eu-south-1': 'ami-0b1db84f31597a70f'
    }
}

AWS_REGION_NAMES = {
    'us-east-1': 'US East (N. Virginia)',
    'us-east-2': 'US East (Ohio)',
    'us-west-1': 'US West (N. California)',
    'us-west-2': 'US West (Oregon)',
    'ca-central-1': 'Canada (Central)',
    'eu-north-1': 'EU (Stockholm)',
    'eu-west-1': 'EU (Ireland)',
    'eu-central-1': 'EU (Frankfurt)',
    'eu-west-2': 'EU (London)',
    'eu-west-3': 'EU (Paris)',
    'ap-northeast-1': 'Asia Pacific (Tokyo)',
    'ap-northeast-2': 'Asia Pacific (Seoul)',
    'ap-northeast-3': 'Asia Pacific (Osaka-Local)',
    'ap-southeast-1': 'Asia Pacific (Singapore)',
    'ap-southeast-2': 'Asia Pacific (Sydney)',
    'ap-south-1': 'Asia Pacific (Mumbai)',
    'sa-east-1': 'South America (Sao Paulo)',  # intentionally no unicode,
    'us-gov-west-1': 'AWS GovCloud (US)',
    'us-gov-east-1': 'AWS GovCloud (US-East)'
}

# Tibanna repo from which awsf scripts are pulled
TIBANNA_REPO_NAME = os.environ.get('TIBANNA_REPO_NAME', '4dn-dcic/tibanna')
TIBANNA_REPO_BRANCH = os.environ.get('TIBANNA_REPO_BRANCH', 'master')
TIBANNA_AWSF_DIR = 'awsf3'

# Tibanna roles
AWS_S3_ROLE_NAME = os.environ.get('AWS_S3_ROLE_NAME', 'S3_access')
S3_ACCESS_ARN = 'arn:aws:iam::' + AWS_ACCOUNT_NUMBER + ':instance-profile/' + AWS_S3_ROLE_NAME

# Profile keys (optional) to use on AWSEM EC2
TIBANNA_PROFILE_ACCESS_KEY = os.environ.get('TIBANNA_PROFILE_ACCESS_KEY', '')
TIBANNA_PROFILE_SECRET_KEY = os.environ.get('TIBANNA_PROFILE_SECRET_KEY', '')

# default step function name
TIBANNA_DEFAULT_STEP_FUNCTION_NAME = os.environ.get('TIBANNA_DEFAULT_STEP_FUNCTION_NAME', 'tibanna_unicorn')

# S3_ENCRYPT_KEY_ID for Tibanna output buckets
S3_ENCRYT_KEY_ID = os.environ.get('S3_ENCRYPT_KEY_ID', None)

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

# Default awsf image
DEFAULT_AWSF_IMAGE = '4dndcic/tibanna-awsf:' + __version__

SFN_TYPE = 'unicorn'
LAMBDA_TYPE = ''
RUN_TASK_LAMBDA_NAME = 'run_task_awsem'
CHECK_TASK_LAMBDA_NAME = 'check_task_awsem'
UPDATE_COST_LAMBDA_NAME = 'update_cost_awsem'


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
