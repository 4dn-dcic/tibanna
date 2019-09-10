# -*- coding: utf-8 -*-
import boto3
from tibanna_cgap.vars import AWS_REGION, LAMBDA_TYPE


config = {
    'function_name': 'status_wfr_' + LAMBDA_TYPE,
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': AWS_REGION,
    'runtime': 'python3.6',
    'role': 'sysadmin',
    'description': 'get_wfr_status',
    'timeout': 300,
    'memory_size': 256
}


def handler(event, context):
    arn = event['executionArn']
    client = boto3.client('stepfunctions', region_name=AWS_REGION)
    run_details = client.describe_execution(
        executionArn=arn
    )

    # handle JSON not serializable stuff
    if run_details.get('startDate'):
        run_details['startDate'] = str(run_details['startDate'])
    if run_details.get('stopDate'):
        run_details['stopDate'] = str(run_details['stopDate'])
    return run_details
