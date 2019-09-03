# -*- coding: utf-8 -*-
# import json
from tibanna_4dn.exceptions import exception_coordinator
from tibanna_4dn.start_run import start_run
from tibanna_4dn.vars import AWS_REGION


config = {
    'function_name': 'start_run_pony',
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': AWS_REGION,
    'runtime': 'python3.6',
    'role': 'lambda_full_s3',
    'description': 'Tibanna pony start_run_awsem',
    'timeout': 300,
    'memory_size': 256
}


def metadata_only(event):
    # this relies on the fact that event contains and output key with output files
    assert event['metadata_only']
    assert event['output_files']
    return real_handler(event, None)


@exception_coordinator('start_run_pony', metadata_only)
def handler(event, context):
    if event.get('push_error_to_end', True):
        event['push_error_to_end'] = True  # push error to end by default for pony
    return real_handler(event, context)


def real_handler(event, context):
    return start_run(event)
