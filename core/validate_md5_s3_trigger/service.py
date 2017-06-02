# -*- coding: utf-8 -*-
import boto3
import json
from core.utils import STEP_FUNCTION_ARN

client = boto3.client('stepfunctions', region_name='us-east-1')


def handler(event, context):
    '''
    this is triggered on completed file upload from s3 and
    event will be set to file data.
    '''
    # get file name
    # print(event)

    upload_key = event['Records'][0]['s3']['object']['key']
    run_name = "validate_%s" % (upload_key.split('/')[1].split('.')[0])

    if event.get('run_name'):
        run_name = event.get('run_name')  # used for testing

    # trigger the step function to run
    response = client.start_execution(
        stateMachineArn=STEP_FUNCTION_ARN,
        name=run_name,
        input=make_input(event),
    )

    # pop no json serializable stuff...
    response.pop('startDate')
    return response


def get_outbucket_name(bucket):
    '''chop up bucket name and have a play'''
    return bucket.replace("files", "wfoutput")


def make_input(event):
    upload_key = event['Records'][0]['s3']['object']['key']
    bucket = event['Records'][0]['s3']['bucket']['name']

    uuid, key = upload_key.split('/')
    data = {"parameters": {},
            "app_name": "md5",
            "workflow_uuid": "d3f25cd3-e726-4b3c-a022-48f844474b41",
            "input_files": [
                {"workflow_argument_name": "input_file",
                 "bucket_name": bucket,
                 "uuid": str(uuid),
                 "object_key": str(key),
                 }
             ],
            "output_bucket": get_outbucket_name(bucket)
            }

    return json.dumps(data)
