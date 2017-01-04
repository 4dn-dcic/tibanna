from __future__ import print_function

import json
import boto3
import os

s3 = boto3.client('s3')
SYS_BUCKET = 'elasticbeanstalk-encoded-4dn-system'
keyfile_name = 'illnevertell'


def get_access_keys():
    return get_key(keyfile_name)['default']


def get_sbg_keys():
    return get_key('sbgkey')


def get_s3_keys():
    return get_key('sbgs3key')


def get_key(keyfile_name='illnevertell'):
    # Share secret encrypted S3 File
    response = s3.get_object(Bucket=SYS_BUCKET,
                             Key=keyfile_name,
                             SSECustomerKey=os.environ.get("SECRET"),
                             SSECustomerAlgorithm='AES256')
    akey = response['Body'].read()
    try:
        return json.loads(akey)
    except ValueError:
        # maybe its not json after all
        return akey


def current_env():
    return os.environ.get('ENV_NAME', 'test')
