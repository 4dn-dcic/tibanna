# -*- coding: utf-8 -*-
import boto3
import json
import uuid
from tibanna.utils import printlog
from tibanna_cgap.vars import (
    AWS_REGION,
    STEP_FUNCTION_ARN,
    LAMBDA_TYPE,
    ACCESSION_PREFIX
)

config = {
    'function_name': 'validate_md5_s3_trigger_' + LAMBDA_TYPE,
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': AWS_REGION,
    'runtime': 'python3.6',
    'role': 'lambda_s3_step_function',
    'description': 'initiates md5/fastqc runs',
    'timeout': 300,
    'memory_size': 256
}


INITIATOR_STEP_FUNCTION_NAME = 'tibanna_initiator_' + LAMBDA_TYPE


def handler(event, context):
    # fix non json-serializable datetime startDate
    if 'Records' in event and 'eventTime' in event['Records']:
        event["Records"]["eventTime"] = str(event["Records"]["eventTime"])

    upload_key = event['Records'][0]['s3']['object']['key']
    accession = upload_key.split('/')[1].split('.')[0]
    if not accession.startswith(ACCESSION_PREFIX):
        printlog("Skipping trigger: not the correct accession prefix %s" % accession)
        return event
    client = boto3.client('stepfunctions', region_name=AWS_REGION)
    response = client.start_execution(
        stateMachineArn=STEP_FUNCTION_ARN(INITIATOR_STEP_FUNCTION_NAME),
        name=accession + '_' + str(uuid.uuid4()),
        input=json.dumps(event),
    )
    printlog(str(response))
    return event
