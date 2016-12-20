from __future__ import print_function

import json
import boto3
import os

print('Loading function')

# pull out into helper lib
s3 = boto3.client('s3')
SYS_BUCKET = 'elasticbeanstalk-encoded-4dn-system'
keyfile_name = 'illnevertell'


def get_access_keys():
    # Share secret encrypted S3 File
    response = s3.get_object(Bucket=SYS_BUCKET,
                             Key=keyfile_name,
                             SSECustomerKey=os.environ.get("SECRET"),
                             SSECustomerAlgorithm='AES256')
    akey = response['Body'].read()
    return json.loads(akey)['default']


def current_env():
    return os.environ.get('ENV_NAME', 'test')


def get_base_url(system):
    urls = {'sbg': {'test': 'https://217gpx7m6i.execute-api.us-east-1.amazonaws.com/dev/'}}

    env = current_env()
    return urls[system][env]


def build_req_parameters(event_data):
    ''' we are assuming we are getting event
    from s3 import create
    '''
    uuid, object_key = event_data['Records'][0]['s3']['object']['key'].split('/')
    bucket = event_data['Records'][0]['s3']['bucket']['name']

    req = {
        "input_files": [
            {
              "bucket_name": bucket,
              "object_key": object_key,
              "uuid": uuid,
              "workflow_argument_name": "input_file"
            }
        ],
        "app_name": "md5",
        "workflow_uuid": "d3f25cd3-e726-4b3c-a022-48f844474b41",
        "parameters": {}
    }
    return json.dumps(req)


def verify_md5(event, context):
    # akeys = get_access_keys()
    print("Received event: " + json.dumps(event, indent=2))
    # workflow_params = build_req_parameters(event)
    # url = get_base_url('sbg')
    # call the workflow function on SBG
    # async request

    # update results

if __name__ == "__main__":
    print(get_access_keys())
