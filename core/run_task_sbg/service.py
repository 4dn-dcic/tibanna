# -*- coding: utf-8 -*-
from core import sbg_utils, utils, ff_utils
import boto3
import logging
LOG = logging.getLogger(__name__)

s3 = boto3.resource('s3')


# check the status and other details of import
def handler(event, context):
    '''
    this is to run the actual task
    '''
    # used to automatically determine the environment
    tibanna_settings = event.get('_tibanna', {})
    tibanna = utils.Tibanna(**tibanna_settings)
    sbg = sbg_utils.create_sbg_workflow(token=tibanna.sbg_keys, **event.get('workflow'))

    pf_meta = event.get('pf_meta')

    # create task on SBG
    LOG.info("sbg task input is %s" % sbg.task_input.__dict__)
    create_resp = sbg.create_task(sbg.task_input)
    LOG.info("create task response is %s" % create_resp)
    if create_resp['status'] != 'DRAFT':
        raise Exception("Failed to create draft task with input %s" % sbg.task_input.__dict__)
    run_response = sbg.run_task()
    LOG.info("run task respons is %s" % run_response)
    if run_response.get('status', 0) == 400:
        raise Exception("Failed to create task with input %s\n detailed info is %s" %
                        (sbg.task_input.__dict__, run_response))

    ff_meta = ff_utils.create_ffmeta(sbg, **event.get('ff_meta'))
    ff_meta.run_status = 'running'
    ff_meta.sbg_task_id = run_response.get('id')

    # make all the file export meta-data stuff here
    # TODO: fix ff_meta mapping issue
    ff_meta.post(key=tibanna.ff_keys)

    return {'workflow': sbg.as_dict(),
            'run_response': run_response,
            'ff_meta': ff_meta.as_dict(),
            'pf_meta': pf_meta,
            "_tibanna": tibanna.as_dict(),
            }
