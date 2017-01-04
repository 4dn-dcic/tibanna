from __future__ import print_function

import json
import boto3
from core import utils

print('Loading function')

# pull out into helper lib
s3 = boto3.client('s3')


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
    akeys = utils.get_access_keys()
    print(akeys)
    print("Received event: " + json.dumps(event, indent=2))
    return build_req_parameters(event)
    # url = get_base_url('sbg')
    # call the workflow function on SBG
    # async request

    # update results
