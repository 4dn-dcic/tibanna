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
    # run_response = event.get('run_response')
    ff_meta = utils.create_ffmeta(**event.get('ff_meta'))
    key = event.get('ff_keys')
    ff_keys = utils.get_access_keys() if not key else key

    # update fourfront with info about the run
    wr = sbg.sbg2workflowrun(ff_meta)
    workflow_post_resp = utils.post_to_metadata(ff_keys, wr, "workflow_run_sbg")

    return{"workflow": sbg.as_dict(),
           "metadata_object": workflow_post_resp,
           "workflowrun": wr}
