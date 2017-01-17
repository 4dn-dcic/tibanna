# -*- coding: utf-8 -*-
from core import utils
import boto3

s3 = boto3.resource('s3')


# check the status and other details of import
def handler(event, context):
    '''
    this is to run the actual task
    '''
    # get data
    sbg = utils.create_sbg_workflow(**event.get('workflow'))

    # create task on SBG
    create_resp = sbg.create_task(sbg.task_input)
    if create_resp['status'] != 'DRAFT':
        raise Exception("Failed to create draft task with input %s" % sbg.task_input)
    run_response = sbg.run_task()

    return {'workflow': sbg.as_dict(),
            'run_response': run_response,
            'workflow_uuid': event.get('workflow_uuid'),
            'metadata_parameters': event.get('metadata_parameters'),
            'metadata_input': event.get('metadata_input')
            }
