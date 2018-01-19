# -*- coding: utf-8 -*-
import boto3
from core.utils import STEP_FUNCTION_ARN
from core.utils import _tibanna_settings
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

    # trigger the step function to run
    response = client.start_execution(
        stateMachineArn=STEP_FUNCTION_ARN,
        name=run_name,
        input=json.dumps(make_input(event)),
    )

    # pop no json serializable stuff...
    response.pop('startDate')
    return response


def get_outbucket_name(bucket):
    '''chop up bucket name and have a play'''
    return bucket.replace("files", "wfoutput")


def make_input(event):
    upload_key = event['Records'][0]['s3']['object']['key']

    uuid, accession = upload_key.split('/')
    return _make_input('fourfront-webprod', 'md5', accession, uuid)


_workflows = {'md5':
              {'uuid': 'd3f25cd3-e726-4b3c-a022-48f844474b41',
               'arg_name': 'input_file'
               },
              'fastqc-0-11-4-1':
              {'uuid': '2324ad76-ff37-4157-8bcc-3ce72b7dace9',
               'arg_name': 'input_fastq'
               },
              }


def _make_input(env, workflow, accession, uuid):
    bucket = "elasticbeanstalk-%s-files" % env
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
                 "object_key": accession,
                 }
             ],
            "output_bucket": output_bucket,
            "config": {
                "ebs_type": "io1",
                "json_bucket": "4dn-aws-pipeline-run-json",
                "ebs_iops": 500,
                "shutdown_min": 30,
                "s3_access_arn": "arn:aws:iam::643366669028:instance-profile/S3_access",
                "ami_id": "ami-cfb14bb5",
                "copy_to_s3": True,
                "script_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/",
                "launch_instance": True,
                "password": "thisisnotmypassword",
                "log_bucket": "tibanna-output",
                "key_name": ""
              },
            }
    data.update(_tibanna_settings({'run_id': str(accession),
                                   'run_type': workflow,
                                   'env': env,
                                   }))
    return data
