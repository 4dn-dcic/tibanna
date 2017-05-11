# -*- coding: utf-8 -*-
from core import sbg_utils
from core.utils import Tibanna
import boto3

s3 = boto3.resource('s3')


def handler(event, context):
    '''
    export output files from sbg to our s3
    '''

    # get data
    # used to automatically determine the environment
    tibanna_settings = event.get('_tibanna', {})
    tibanna = Tibanna(**tibanna_settings)
    sbg = sbg_utils.create_sbg_workflow(token=tibanna.sbg_keys, **event.get('workflow'))
    run_response = event.get('run_response')
    ff_meta = event.get('ff_meta')
    uuid = ff_meta['uuid']
    pf_meta = event.get('pf_meta')

    if run_response in ['FAILED', 'ABORTED']:
        raise Exception("workflow run failed or aborted")

    sbg.export_all_output_files(run_response, ff_meta, base_dir=uuid)
    # creating after we export will add output file info to ff_meta
    ff_meta = sbg_utils.create_ffmeta(sbg, **event.get('ff_meta'))
    ff_meta.run_status = "output_files_transferring"
    for pf in pf_meta:
        pf['status'] = "uploading"
    # we still need a code for patching.

    return {'workflow': sbg.as_dict(),
            'ff_meta': ff_meta.as_dict(),
            # 'pf_meta': [pf.as_dict() for pf in pf_meta]
            'pf_meta': pf_meta,
            '_tibanna': tibanna.as_dict()
            }
