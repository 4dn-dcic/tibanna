# -*- coding: utf-8 -*-
from core.utils import STEP_FUNCTION_ARN, AWS_REGION
from core.utils import printlog
import boto3
import json
import uuid

INITIATOR_STEP_FUNCTION_NAME = 'tibanna_initiator'


def handler(event, context):
    # fix non json-serializable datetime startDate
    if 'Records' in event and 'eventTime' in event['Records']:
        event["Records"]["eventTime"] = str(event["Records"]["eventTime"])

    upload_key = event['Records'][0]['s3']['object']['key']
    run_name = upload_key.split('/')[1].split('.')[0]

    client = boto3.client('stepfunctions', region_name=AWS_REGION)
    response = client.start_execution(
        stateMachineArn=STEP_FUNCTION_ARN(INITIATOR_STEP_FUNCTION_NAME),
        name=run_name + '_' + str(uuid.uuid4()),
        input=json.dumps(event),
    )
    printlog(str(response))
    return event
