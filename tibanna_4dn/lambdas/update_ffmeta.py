# -*- coding: utf-8 -*-
from tibanna_ffcommon.exceptions import exception_coordinator
from tibanna_4dn.update_ffmeta import update_ffmeta
from tibanna_4dn.vars import AWS_REGION, LAMBDA_TYPE

config = {
    'function_name': 'update_ffmeta_' + LAMBDA_TYPE,
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': AWS_REGION,
    'runtime': 'python3.6',
    'role': 'lambda_full_s3',
    'description': 'Tibanna pony update_ffmeta',
    'timeout': 300,
    'memory_size': 256
}


def metadata_only(event):
    # just create a fake awsem config so the handler function does it's magic
    '''
    if not event.get('args'):
        event['args'] = {'app_name': event['ff_meta'].get('awsem_app_name'),
                         'output_S3_bucket': 'metadata_only',
                         'output_target': {'metadata_only': 'metadata_only'}
                         }

    if not event.get('config'):
        event['config'] = {'runmode': 'metadata_only'}
    '''
    return real_handler(event, None)


@exception_coordinator('update_ffmeta', metadata_only)
def handler(event, context):
    return real_handler(event, context)


def real_handler(event, context):
    return update_ffmeta(event)
