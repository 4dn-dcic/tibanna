# -*- coding: utf-8 -*-
from core import utils
import boto3

s3 = boto3.resource('s3')


# check the status and other details of import
def handler(event, context):
    '''
    this is to check if the task run is done:
    http://docs.sevenbridges.com/reference#get-task-execution-details
    '''
    # get data
    sbg = utils.create_sbg_workflow(**event.get('workflow'))

    # check status of workflow, error if not done
    status = sbg.check_task()
    if not status['status'] in ['DONE', 'COMPLETED']:
        data = {'workflow': sbg.as_dict(),
                'status': status}
        raise Exception('Task not finished => %s' % data)

    return {'workflow': sbg.as_dict(),
            'run_response': status,
            'workflow_uuid': event.get('workflow_uuid'),
            'metadata_parameters': event.get('metadata_parameters'),
            }
