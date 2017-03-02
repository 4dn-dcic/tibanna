# -*- coding: utf-8 -*-
from core import utils
import boto3

s3 = boto3.resource('s3')


def create_processed_file_metadata(status, sbg, ff_meta):
    try:
        pf_meta = ff_meta.create_processed_file_metadata(status=status, sbg=sbg)
        raise Exception("pf_meta = {}".format(str(pf_meta)))
    except Exception as e:
        raise Exception("Unable to create processed file metadata json : %s" % e)
    try:
        if pf_meta:
            ff_key = utils.get_access_keys()
            for pf in pf_meta:
                pf.post(key=ff_key)
    except Exception as e:
        raise Exception("Unable to post processed file metadata : %s" % e)
    return pf_meta


def handler(event, context):
    '''
    export output files from sbg to our s3
    '''

    # get data
    sbg = utils.create_sbg_workflow(**event.get('workflow'))
    run_response = event.get('run_response')
    ff_meta = event.get('ff_meta')
    uuid = ff_meta['uuid']

    sbg.export_all_output_files(run_response, ff_meta, base_dir=uuid)
    # creating after we export will add output file info to ff_meta
    ff_meta = utils.create_ffmeta(sbg, **event.get('ff_meta'))
    ff_meta.run_status = "output_files_transferring"

    # create processed file metadata here, because
    # 1) we want to keep track of the uploading status and
    # 2) we want to specify directory and file name before we export
    # (these files can be large so don't change file name after the export which is equivalent to rewriting)
    tmp = ff_meta.output_files
    tmp2 = sbg.export_report
    pf_meta = create_processed_file_metadata("uploading", sbg, ff_meta)

    return {'workflow': sbg.as_dict(),
            'ff_meta': ff_meta.as_dict(),
            'tmp': tmp,
            'tmp2': tmp2
            # 'pf_meta': [pf.as_dict() for pf in pf_meta]
            }
