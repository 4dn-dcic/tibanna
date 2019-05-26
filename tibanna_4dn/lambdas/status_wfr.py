# -*- coding: utf-8 -*-
import boto3
from .vars.Vars import AWS_REGION


config = {
    'function_name': 'status_wfr',
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': AWS_REGION,
    'runtime': 'python3.6',
    'role': 'tibanna_lambda_init_role',
    'description': 'get_wfr_status',
    'timeout': 300,
    'memory_size': 256
}


def handler(event, context):
    arn = event['executionArn']
    client = boto3.client('stepfunctions', region_name='us-east-1')
    run_details = client.describe_execution(
        executionArn=arn
    )

    # handle JSON not serializable stuff
    if run_details.get('startDate'):
        run_details['startDate'] = str(run_details['startDate'])
    if run_details.get('stopDate'):
        run_details['stopDate'] = str(run_details['stopDate'])
    return run_details
