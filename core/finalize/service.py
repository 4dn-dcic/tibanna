# -*- coding: utf-8 -*-
from core import sbg_utils, utils, ff_utils
import boto3

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
    ff_meta = ff_utils.create_ffmeta(sbg, **event.get('ff_meta'))

    # TODO: check a whole bunch of stuff here maybe...
    if ff_meta.run_status == "output_file_transfer_finished":
        ff_meta.run_status = 'complete'
    else:
        ff_meta.run_status = 'error'
        ff_meta.description = ('set to error because status comming into finalize was not' +
                               ' output_file_transfer_finished as expected')

    # make all the file export meta-data stuff here
    # TODO: fix ff_meta mapping issue
    ff_meta.post(key=tibanna.ff_keys)

    return {'workflow': sbg.as_dict(),
            'ff_meta': ff_meta.as_dict(),
            "_tibanna": tibanna.as_dict(),
            }
