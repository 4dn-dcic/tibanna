# -*- coding: utf-8 -*-
from tibanna.utils import powerup
from tibanna_4dn.update_ffmeta import update_ffmeta


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


@powerup('update_ffmeta_awsem', metadata_only)
def handler(event, context):
    return real_handler(event, context)


def real_handler(event, context):
    return update_ffmeta(event)
