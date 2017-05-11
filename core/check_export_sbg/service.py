# -*- coding: utf-8 -*-
from core import utils, sbg_utils
import boto3
from collections import defaultdict
from core.fastqc_utils import parse_fastqc


s3 = boto3.resource('s3')


def donothing(status, sbg, ff_meta, ff_key=None):
    return None


def update_processed_file_metadata(status, pf_meta, tibanna):

    ff_key = tibanna.ff_keys
    try:
        for pf in pf_meta:
            pf['status'] = status
    except Exception as e:
        raise Exception("Unable to update processed file metadata json : %s" % e)
    try:
        for pf in pf_meta:
            pfo = sbg_utils.ProcessedFileMetadata(**pf)
            pfo.post(key=ff_key)
    except Exception as e:
        raise Exception("Unable to post processed file metadata : %s" % e)
    return pf_meta


def fastqc_updater(status, sbg, ff_meta, tibanna):
    # keys
    ff_key = tibanna.ff_keys
    # move files to proper s3 location
    accession = get_inputfile_accession(sbg, input_file_name='input_fastq')
    zipped_report = ff_meta.output_files[0]['upload_key'].strip()
    files_to_parse = ['summary.txt', 'fastqc_data.txt', 'fastqc_report.html']
    try:
        files = tibanna.s3.unzip_s3_to_s3(zipped_report, accession, files_to_parse)
    except Exception as e:
        raise Exception("%s (key={})\n".format(zipped_report) % e)
    # parse fastqc metadata
    meta = parse_fastqc(files['summary.txt']['data'],
                        files['fastqc_data.txt']['data'],
                        url=files['fastqc_report.html']['s3key'])

    # post fastq metadata
    qc_meta = sbg_utils.post_to_metadata(meta, 'quality_metric_fastqc', key=ff_key)
    if qc_meta.get('@graph'):
        qc_meta = qc_meta['@graph'][0]

    # update original file as well
    try:
        original_file = sbg_utils.get_metadata(accession, key=ff_key)
    except Exception as e:
        raise Exception("Couldn't get metadata for accession {} : ".format(accession) +
                        "original_file ={}\n".format(str(original_file)) % e)
    patch_file = {'quality_metric': qc_meta['@id']}
    try:
        sbg_utils.patch_metadata(patch_file, original_file['uuid'], key=ff_key)
    except Exception as e:
        raise Exception("patch_metadata failed in fastqc_updater. %s. " +
                        "original_file ={}\n".format(str(original_file)) % e)

    # nothing to patch to ff_meta
    return {"output_quality_metrics": [{"name": "quality_metric_fastqc", "value": qc_meta['@id']}]}


def md5_updater(status, sbg, ff_meta, tibanna):

    # get key
    ff_key = tibanna.ff_keys
    # get metadata about original input file
    accession = get_inputfile_accession(sbg)
    original_file = sbg_utils.get_metadata(accession, key=ff_key)

    if status == 'uploaded':
        md5 = utils.read_s3(ff_meta.output_files[0]['upload_key']).strip()
        original_md5 = original_file.get('content_md5sum', False)
        if original_md5 and original_md5 != md5:
            # file status to be upload failed / md5 mismatch
            print("no matcho")
            md5_updater("upload failed", sbg, ff_meta, tibanna)
        else:
            new_file = {}
            new_file['status'] = 'uploaded'
            new_file['content_md5sum'] = md5

            sbg_utils.patch_metadata(new_file, accession, key=ff_key)
    elif status == 'upload failed':
            new_file = {}
            new_file['status'] = 'upload failed'
            sbg_utils.patch_metadata(new_file, original_file['uuid'], key=ff_key)

    # nothing to patch to ff_meta
    return None


def get_inputfile_accession(sbg, input_file_name='input_file'):
        return sbg.task_input.inputs[input_file_name]['name'].split('.')[0].strip('/')


# check the status and other details of import
def handler(event, context):
    '''
    this is to check if the task run is done:
    http://docs.sevenbridges.com/reference#get-task-execution-details
    '''
    # get data
    # used to automatically determine the environment
    tibanna_settings = event.get('_tibanna', {})
    tibanna = utils.Tibanna(**tibanna_settings)
    sbg = sbg_utils.create_sbg_workflow(token=tibanna.sbg_keys, **event.get('workflow'))
    ff_meta = sbg_utils.create_ffmeta(sbg, **event.get('ff_meta'))
    pf_meta = event.get('pf_meta')
    # ensure this bad boy is always initialized
    patch_meta = False

    for idx, export in enumerate(sbg.export_report):
        upload_key = export['upload_key']
        export_id = export['export_id']
        export_res = sbg.check_export(export_id)
        print("export res is %s", export_res)
        status = export_res.get('state')
        sbg.export_report[idx]['status'] = status
        if status == 'COMPLETED':
            patch_meta = OUTFILE_UPDATERS[sbg.app_name]('uploaded', sbg, ff_meta, tibanna)
            if pf_meta:
                pf_meta = update_processed_file_metadata('uploaded', pf_meta, tibanna)
        elif status in ['PENDING', 'RUNNING']:
            patch_meta = OUTFILE_UPDATERS[sbg.app_name]('uploading', sbg, ff_meta, tibanna)
            raise Exception("Export of file %s is still running" % upload_key)
        elif status in ['FAILED']:
            patch_meta = OUTFILE_UPDATERS[sbg.app_name]('upload failed', sbg, ff_meta, tibanna)
            raise Exception("Failed to export file %s \n sbg result: %s" % (upload_key, export_res))

    # if we got all the exports let's go ahead and update our ff_metadata object
    ff_meta.run_status = "output_file_transfer_finished"

    # allow for a simple way for updater to add appropriate meta_data
    if patch_meta:
        ff_meta.__dict__.update(patch_meta)

    # make all the file export meta-data stuff here
    # TODO: fix bugs with ff_meta mapping for output and input file
    ff_meta.post(key=tibanna.ff_keys)

    return {'workflow': sbg.as_dict(),
            'ff_meta': ff_meta.as_dict(),
            'pf_meta': pf_meta,
            '_tibanna': tibanna.as_dict()
            }


# Cardinal knowledge of all workflow updaters
OUTFILE_UPDATERS = defaultdict(lambda: donothing)
OUTFILE_UPDATERS['md5'] = md5_updater
OUTFILE_UPDATERS['validatefiles'] = md5_updater
OUTFILE_UPDATERS['fastqc-0-11-4-1'] = fastqc_updater
