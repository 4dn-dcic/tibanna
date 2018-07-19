# -*- coding: utf-8 -*-
import boto3
from core.utils import _tibanna_settings, STEP_FUNCTION_ARN
from core.pony_utils import Tibanna
from dcicutils.ff_utils import get_metadata
import json

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

    # only run if status is uploading...
    is_uploading = is_status_uploading(event)
    if event.get('force_run'):
        is_uploading = True
    if is_uploading:
        # trigger the step function to run
        response = client.start_execution(
            stateMachineArn=STEP_FUNCTION_ARN,
            name=run_name,
            input=json.dumps(make_input(event)),
        )

        # pop no json serializable stuff...
        response.pop('startDate')
        return response
    else:
        return {'info': 'status is not uploading'}


def is_status_uploading(event):
    print("is status uploading: %s" % event)
    upload_key = event['Records'][0]['s3']['object']['key']
    if upload_key.endswith('html'):
        return False

    uuid, object_key = upload_key.split('/')
    accession = object_key.split('.')[0]

    # guess env from bucket name
    bucket = event['Records'][0]['s3']['bucket']['name']
    env = '-'.join(bucket.split('-')[1:3])

    tibanna = Tibanna(env=env)
    meta = get_metadata(accession,
                        key=tibanna.ff_keys,
                        ff_env=env,
                        add_on='frame=object',
                        check_queue=True)
    if meta:
        return meta.get('status', '') == 'uploading'
    else:
        return False


def get_outbucket_name(bucket):
    '''chop up bucket name and have a play'''
    return bucket.replace("files", "wfoutput")


def make_input(event):
    upload_key = event['Records'][0]['s3']['object']['key']

    uuid, object_key = upload_key.split('/')

    # guess env from bucket name
    bucket = event['Records'][0]['s3']['bucket']['name']
    env = '-'.join(bucket.split('-')[1:3])

    return _make_input(env, bucket, 'md5', object_key, uuid)


_workflows = {'md5':
              {'uuid': 'd3f25cd3-e726-4b3c-a022-48f844474b41',
               'arg_name': 'input_file'
               },
              'fastqc-0-11-4-1':
              {'uuid': '2324ad76-ff37-4157-8bcc-3ce72b7dace9',
               'arg_name': 'input_fastq'
               },
              }


def _make_input(env, bucket, workflow, object_key, uuid):
    output_bucket = "elasticbeanstalk-%s-wfoutput" % env
    workflow_uuid = _workflows[workflow]['uuid']
    workflow_arg_name = _workflows[workflow]['arg_name']

    data = {"parameters": {},
            "app_name": workflow,
            "workflow_uuid": workflow_uuid,
            "input_files": [
                {"workflow_argument_name": workflow_arg_name,
                 "bucket_name": bucket,
                 "uuid": uuid,
                 "object_key": object_key,
                 }
             ],
            "output_bucket": output_bucket,
            "config": {
                "ebs_type": "io1",
                "json_bucket": "4dn-aws-pipeline-run-json",
                "ebs_iops": 500,
                "shutdown_min": 30,
                "copy_to_s3": True,
                "launch_instance": True,
                "password": "thisisnotmypassword",
                "log_bucket": "tibanna-output",
                "key_name": ""
              },
            }
    data.update(_tibanna_settings({'run_id': str(object_key),
                                   'run_type': workflow,
                                   'env': env,
                                   }))
    return data
