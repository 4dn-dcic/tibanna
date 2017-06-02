# -*- coding: utf-8 -*-
from core import sbg_utils, ff_utils
from core.utils import Tibanna
import boto3
import logging

LOG = logging.getLogger(__name__)

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
    ff_meta = ff_utils.create_ffmeta(sbg, **event.get('ff_meta'))

    # check status of workflow, error if not done
    status = sbg.check_task()
    LOG.info("status of sbg task is %s" % status)

    if not status['status'] in ['DONE', 'COMPLETED', 'FAILED']:
        data = {'workflow': sbg.as_dict(),
                'status': status}
        raise sbg_utils.SBGStillRunningException('Task not finished => %s' % data)

    if status['status'] == 'FAILED':
        ff_meta.run_status = 'error'
        ff_meta.description = 'SBG task %s reported FAILED status' % sbg.task_id
        ff_meta.post(key=tibanna.ff_keys)

    # TODO: handle only specific errors so this can terminate the rest of the workflow

    return {'workflow': sbg.as_dict(),
            'run_response': status,
            'ff_meta': ff_meta.as_dict(),
            'pf_meta': event.get('pf_meta'),
            '_tibanna': tibanna.as_dict(),
            }
