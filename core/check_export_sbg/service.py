# -*- coding: utf-8 -*-
from core import utils
import boto3
from collections import defaultdict

s3 = boto3.resource('s3')
ff_key = utils.get_access_keys()


def update_processed_file_metadata(status, sbg, ff_meta):
    return ff_meta.update_processed_file_metadata(status=status)


def md5_updater(status, sbg, ff_meta):

    # create / update Workflow run object
    # del ff_meta.output_files
    # ff_meta.post(key=utils.get_access_keys())
    # don't bother with update_processed_file_metadata stuff
    # based on status, update file object

    '''
        if status == 'COMPLETED':
            OUTFILE_UPDATERS[sbg.app_name]('upladed', sbg, ff_meta)
            # ff_meta.update_processed_file_metadata(status='uploaded')
        elif status in ['PENDING', 'RUNNING']:
            OUTFILE_UPDATERS[sbg.app_name]('uplading', sbg, ff_meta)
            raise Exception("Export of file %s is still running" % filename)
        elif status in ['FAILED']:
    '''
    # file to update -- thats the uuid
    original_file = utils.get_metadata(ff_meta.input_files[0]['value'], key=ff_key)

    if status == 'uploaded':
        md5 = utils.read_s3(ff_meta.output_files[0]['filename']).strip()
        original_md5 = original_file.get('content_md5sum', False)
        if original_md5 and original_md5 != md5:
            # file status to be upload failed / md5 mismatch
            print("no matcho")
            md5_updater("upload failed", sbg, ff_meta)
        else:
            new_file = {}
            new_file['status'] = 'uploaded'
            new_file['content_md5sum'] = md5

            utils.patch_metadata(new_file, original_file['uuid'], key=ff_key)
    elif status == 'upload failed':
            new_file = {}
            new_file['status'] = 'upload failed'
            utils.patch_metadata(new_file, original_file['uuid'], key=ff_key)


# check the status and other details of import
def handler(event, context):
    '''
    this is to check if the task run is done:
    http://docs.sevenbridges.com/reference#get-task-execution-details
    '''
    # get data
    sbg = utils.create_sbg_workflow(**event.get('workflow'))
    ff_meta = utils.create_ffmeta(sbg, **event.get('ff_meta'))

    for idx, export in enumerate(sbg.export_report):
        filename = export['filename']
        export_id = export['export_id']
        export_res = sbg.check_export(export_id)
        status = export_res.get('state')
        sbg.export_report[idx]['status'] = status
        if status == 'COMPLETED':
            OUTFILE_UPDATERS[sbg.app_name]('uploaded', sbg, ff_meta)
            # ff_meta.update_processed_file_metadata(status='uploaded')
        elif status in ['PENDING', 'RUNNING']:
            OUTFILE_UPDATERS[sbg.app_name]('uploading', sbg, ff_meta)
            raise Exception("Export of file %s is still running" % filename)
        elif status in ['FAILED']:
            OUTFILE_UPDATERS[sbg.app_name]('upload failed', sbg, ff_meta)
            raise Exception("Failed to export file %s \n sbg result: %s" % (filename, export_res))

    # if we got all the exports let's go ahead and update our ff_metadata object
    ff_meta.run_status = "output_file_transfer_finished"
    # make all the file export meta-data stuff here

    return {'workflow': sbg.as_dict(),
            'ff_meta': ff_meta.as_dict()
            }

# Cardinal knowledge of all workflow updaters
OUTFILE_UPDATERS = defaultdict(lambda: update_processed_file_metadata)
OUTFILE_UPDATERS['md5'] = md5_updater
OUTFILE_UPDATERS['validatefiles'] = md5_updater
