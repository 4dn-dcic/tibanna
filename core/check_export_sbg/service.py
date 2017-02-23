# -*- coding: utf-8 -*-
from core import utils
import boto3
from collections import defaultdict
from core.fastqc_utils import parse_fastqc


s3 = boto3.resource('s3')
ff_key = utils.get_access_keys()


def update_processed_file_metadata(status, sbg, ff_meta):
    return ff_meta.update_processed_file_metadata(status=status, sbg=sbg)


def fastqc_updater(status, sbg, ff_meta):
    # move files to proper s3 location
    accession = get_inputfile_accession(sbg, input_file_name='input_fastq')
    zipped_report = ff_meta.output_files[0]['filename'].strip()
    files_to_parse = ['summary.txt', 'fastqc_data.txt', 'fastqc_report.html']
    files = utils.unzip_s3_to_s3(zipped_report, accession, files_to_parse)
    # parse fastqc metadata
    meta = parse_fastqc(files['summary.txt']['data'],
                        files['fastqc_data.txt']['data'],
                        url=files['fastqc_report.html']['s3key'])

    # post fastq metadata
    qc_meta = utils.post_to_metadata(meta, 'quality_metric_fastqc', key=ff_key)
    if qc_meta.get('@graph'):
        qc_meta = qc_meta['@graph'][0]

# update original file as well
    original_file = utils.get_metadata(accession, key=ff_key)
    patch_file = {'quality_metric': qc_meta['@id']}
    utils.patch_metadata(patch_file, original_file['uuid'], key=ff_key)


def md5_updater(status, sbg, ff_meta):
    # get metadata about original input file
    accession = get_inputfile_accession(sbg)
    original_file = utils.get_metadata(accession, key=ff_key)

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

            utils.patch_metadata(new_file, accession, key=ff_key)
    elif status == 'upload failed':
            new_file = {}
            new_file['status'] = 'upload failed'
            utils.patch_metadata(new_file, original_file['uuid'], key=ff_key)


def get_inputfile_accession(sbg, input_file_name='input_file'):
        return sbg.task_input.inputs[input_file_name]['name'].split('.')[0].strip('/')


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
            patch_meta = OUTFILE_UPDATERS[sbg.app_name]('uploaded', sbg, ff_meta)
            # ff_meta.update_processed_file_metadata(status='uploaded')
        elif status in ['PENDING', 'RUNNING']:
            patch_meta = OUTFILE_UPDATERS[sbg.app_name]('uploading', sbg, ff_meta)
            raise Exception("Export of file %s is still running" % filename)
        elif status in ['FAILED']:
            patch_meta = OUTFILE_UPDATERS[sbg.app_name]('upload failed', sbg, ff_meta)
            raise Exception("Failed to export file %s \n sbg result: %s" % (filename, export_res))

    # if we got all the exports let's go ahead and update our ff_metadata object
    ff_meta.run_status = "output_file_transfer_finished"

    # allow for a simple way for updater to add appropriate meta_data
    if patch_meta:
        ff_meta.__dict__.update(patch_meta)

    # make all the file export meta-data stuff here
    # TODO: fix bugs with ff_meta mapping for output and input file
    ff_meta.post(key=utils.get_access_keys())

    return {'workflow': sbg.as_dict(),
            'ff_meta': ff_meta.as_dict()
            }


# Cardinal knowledge of all workflow updaters
OUTFILE_UPDATERS = defaultdict(lambda: update_processed_file_metadata)
OUTFILE_UPDATERS['md5'] = md5_updater
OUTFILE_UPDATERS['validatefiles'] = md5_updater
OUTFILE_UPDATERS['fastqc-0-11-4-1'] = fastqc_updater
