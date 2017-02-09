# -*- coding: utf-8 -*-
from core import utils
import boto3

s3 = boto3.resource('s3')


def handler(event, context):
    '''
    export output files from sbg to our s3
    '''

    # get data
    sbg = utils.create_sbg_workflow(**event.get('workflow'))
    uuid = event['ff_meta']['uuid']
    run_response = event.get('run_response')

    sbg.export_all_output_files(run_response, base_dir=uuid)
    # creating after we export will add output file info to ff_meta
    ff_meta = utils.create_ffmeta(sbg, **event.get('ff_meta'))
    ff_meta.run_status = "output_files_transferring"

    return {'workflow': sbg.as_dict(),
            'ff_meta': ff_meta.as_dict()
            }
