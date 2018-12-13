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
    accession = upload_key.split('/')[1].split('.')[0]
    if not accession.startswith('4DN'):
        printlog("Skipping trigger: not 4DN accession %s" % accession)
        return event
    client = boto3.client('stepfunctions', region_name=AWS_REGION)
    response = client.start_execution(
        stateMachineArn=STEP_FUNCTION_ARN(INITIATOR_STEP_FUNCTION_NAME),
        name=accession + '_' + str(uuid.uuid4()),
        input=json.dumps(event),
    )
    printlog(str(response))
    return event
