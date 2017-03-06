# -*- coding: utf-8 -*-
from core import sbg_utils
import boto3

s3 = boto3.resource('s3')


# check the status and other details of import
def handler(event, context):
    '''
    this is to check if the task run is done:
    http://docs.sevenbridges.com/reference#get-task-execution-details
    '''
    # get data
    sbg = sbg_utils.create_sbg_workflow(**event.get('workflow'))

    # check status of workflow, error if not done
    status = sbg.check_task()
    if not status['status'] in ['DONE', 'COMPLETED', 'FAILED']:
        data = {'workflow': sbg.as_dict(),
                'status': status}
        raise Exception('Task not finished => %s' % data)

    return {'workflow': sbg.as_dict(),
            'run_response': status,
            'ff_meta': event.get('ff_meta')
            }
