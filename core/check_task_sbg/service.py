# -*- coding: utf-8 -*-
from core import sbg_utils
from core.utils import Tibanna
import boto3

s3 = boto3.resource('s3')


# check the status and other details of import
def handler(event, context):
    '''
    this is to check if the task run is done:
    http://docs.sevenbridges.com/reference#get-task-execution-details
    '''
    # used to automatically determine the environment
    tibanna_settings = event.get('_tibanna', {})
    tibanna = Tibanna(**tibanna_settings)
    sbg = sbg_utils.create_sbg_workflow(token=tibanna.sbg_keys, **event.get('workflow'))

    # check status of workflow, error if not done
    status = sbg.check_task()
    if not status['status'] in ['DONE', 'COMPLETED', 'FAILED']:
        data = {'workflow': sbg.as_dict(),
                'status': status}
        raise Exception('Task not finished => %s' % data)

    return {'workflow': sbg.as_dict(),
            'run_response': status,
            'ff_meta': event.get('ff_meta'),
            'pf_meta': event.get('pf_meta'),
            '_tibanna': tibanna.as_dict(),
            }
