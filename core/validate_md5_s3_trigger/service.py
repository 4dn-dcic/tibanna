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
    client = boto3.client('stepfunctions', region_name=AWS_REGION)
    response = client.start_execution(
        stateMachineArn=STEP_FUNCTION_ARN(INITIATOR_STEP_FUNCTION_NAME),
        name=str(uuid.uuid4()),
        input=json.dumps(event),
    )
    printlog(str(response))
    return event
