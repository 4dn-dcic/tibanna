# -*- coding: utf-8 -*-
import requests
import json
import copy
import boto3
from collections import defaultdict
from dcicutils import ff_utils
from .pony_utils import (
  FormatExtensionMap,
  get_extra_file_key,
  ProcessedFileMetadata,
  Awsem,
  TibannaSettings,
  create_ffmeta_awsem,
  parse_formatstr,
  register_to_higlass
)
from tibanna.utils import (
    printlog,
)
from .exceptions import (
    TibannaStartException,
)
from .fastqc_utils import parse_qc_table


def donothing(status, sbg, ff_meta, ff_key=None, **kwargs):
    return None


def add_higlass_to_pf(pf, tbn, awsemfile):
    def register_to_higlass_bucket(key, file_format, file_type):
        return register_to_higlass(tbn, awsemfile.bucket, key, file_format, file_type)

    if awsemfile.bucket in ff_utils.HIGLASS_BUCKETS:
        higlass_uid = None
        for hgcf in higlass_config:
            if pf.file_format == hgcf['file_format']:
                if not hgcf['extra']:
                    higlass_uid = register_to_higlass_bucket(awsemfile.key, hgcf['file_type'], hgcf['data_type'])
                else:
                    for pfextra in pf.extra_files:
                    if pfextra.get('file_format') == hgcf['extra']:
                        fe_map = FormatExtensionMap(tbn.ff_keys)
                        extra_file_key = get_extra_file_key('bg', awsemfile.key, 'bw', fe_map)
                        higlass_uid = register_to_higlass_bucket(extra_file_key, hgcf['file_type'], hgcf['data_type'])
        pf.add_higlass_uid(higlass_uid)


def add_md5_filesize_to_pf(pf, awsemfile):
    if not awsemfile.is_extra:
        pf.status = 'uploaded'
        if awsemfile.md5:
            pf.md5sum = awsemfile.md5
        if awsemfile.filesize:
            pf.file_size = awsemfile.filesize


def add_md5_filesize_to_pf_extra(pf, awsemfile):
    printlog("awsemfile.is_extra=%s" % awsemfile.is_extra)
    if awsemfile.is_extra:
        for pfextra in pf.extra_files:
            printlog("pfextra : %s" % str(pfextra))
            printlog("awsemfile.format_if_extra : %s" % awsemfile.format_if_extra)
            if pfextra.get('file_format') == awsemfile.format_if_extra:
                if awsemfile.md5:
                    pfextra['md5sum'] = awsemfile.md5
                if awsemfile.filesize:
                    pfextra['file_size'] = awsemfile.filesize
        printlog("add_md5_filesize_to_pf_extra: %s" % pf.extra_files)


def qc_updater(status, awsemfile, ff_meta, tbn, other_fields=None):
    if ff_meta.awsem_app_name == 'fastqc-0-11-4-1':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_fastqc',
                           file_argument='input_fastq',
                           report_html='fastqc_report.html',
                           datafiles=['summary.txt', 'fastqc_data.txt'],
                           other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'pairsqc-single':
        file_argument = 'input_pairs'
        input_accession = str(awsemfile.runner.get_file_accessions(file_argument)[0])
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric="quality_metric_pairsqc",
                           file_argument=file_argument, report_html='pairsqc_report.html',
                           datafiles=[input_accession + '.summary.out'],
                           other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'repliseq-parta':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_dedupqc_repliseq',
                           file_argument='filtered_sorted_deduped_bam',
                           datafiles=['summary.txt'],
                           other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'chip-seq-alignment':
        input_accession = str(awsemfile.runner.get_file_accessions('fastqs')[0])
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_flagstat_qc',
                           file_argument='bam',
                           datafiles=[input_accession + '.merged.trim_50bp.' + 'flagstat.qc'],
                           other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'encode-chipseq':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_chipseq',
                           file_argument='chip.peak_calls',
                           report_html=awsemfile.key,
                           datafiles=[], zipped=False,
                           other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'encode-chipseq-aln-chip':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_chipseq',
                           file_argument='chip.first_ta',
                           datajson_argument='chip.qc_json',
                           report_html=awsemfile.key,
                           datafiles=[], zipped=False, other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'encode-chipseq-aln-ctl':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_chipseq',
                           file_argument='chip.first_ta_ctl',
                           datajson_argument='chip.qc_json',
                           report_html=awsemfile.key,
                           datafiles=[], zipped=False, other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'encode-chipseq-postaln':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_chipseq',
                           file_argument='chip.optimal_peak',
                           datajson_argument='chip.qc_json',
                           report_html=awsemfile.key,
                           datafiles=[], zipped=False, other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'encode-atacseq':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_atacseq',
                           file_argument='atac.peak_calls',
                           report_html=awsemfile.key,
                           datafiles=[], zipped=False, other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'encode-atacseq-aln':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_atacseq',
                           file_argument='atac.first_ta',
                           datajson_argument='atac.qc_json',
                           report_html=awsemfile.key,
                           datafiles=[], zipped=False, other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'encode-atacseq-postaln':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_atacseq',
                           file_argument='atac.optimal_peak',
                           datajson_argument='atac.qc_json',
                           report_html=awsemfile.key,
                           datafiles=[], zipped=False, other_fields=other_fields)
    elif ff_meta.awsem_app_name == 'MARGI':
        return _qc_updater(status, awsemfile, ff_meta, tbn,
                           quality_metric='quality_metric_margi',
                           file_argument='final_pairs',
                           datafiles=['qc_report.txt'],
                           other_fields=other_fields)


def _qc_updater(status, awsemfile, ff_meta, tbn, quality_metric='quality_metric_fastqc',
                file_argument='input_fastq', report_html=None,
                datafiles=None, zipped=True, datajson_argument=None, other_fields=None):
    if datajson_argument == awsemfile.argument_name:
        return
    # avoid using [] as default argument
    if datafiles is None:
        datafiles = ['summary.txt', 'fastqc_data.txt']
    if status == 'uploading':
        # wait until this bad boy is finished
        return
    # keys
    ff_key = tbn.ff_keys
    # move files to proper s3 location
    # need to remove sbg from this line
    accession = awsemfile.runner.get_file_accessions(file_argument)[0]
    zipped_report = awsemfile.key
    files_to_parse = datafiles
    if report_html:
        files_to_parse.append(report_html)
    printlog("accession is %s" % accession)
    jsondata = dict()
    if zipped:
        try:
            files = awsemfile.s3.unzip_s3_to_s3(zipped_report, accession, files_to_parse,
                                                acl='public-read')
        except Exception as e:
            printlog(tbn.s3.__dict__)
            raise Exception("%s (key={})\n".format(zipped_report) % e)
        printlog("files : %s" % str(files))
        filedata = [files[_]['data'].decode('utf-8', 'backslashreplace') for _ in datafiles]
    else:
        if datajson_argument:
            datajson_key = awsemfile.runner.get_file_key(datajson_argument)
            jsondata0 = [json.loads(awsemfile.s3.read_s3(_).decode('utf-8', 'backslashreplace')) for _ in datajson_key]
            for d in jsondata0:
                jsondata.update(d)
        filedata = [awsemfile.s3.read_s3(_).decode('utf-8', 'backslashreplace') for _ in datafiles]
        reportdata = awsemfile.s3.read_s3(report_html).decode('utf-8', 'backslashreplace')
        report_html = accession + 'qc_report.html'
        awsemfile.s3.s3_put(reportdata.encode(), report_html, acl='public-read')
        qc_url = 'https://s3.amazonaws.com/' + awsemfile.bucket + '/' + report_html
        files = {report_html: {'data': reportdata, 's3key': qc_url}}
    # schema. do not need to check_queue
    qc_schema = ff_utils.get_metadata("profiles/" + quality_metric + ".json",
                                      key=ff_key,
                                      ff_env=tbn.env)
    # parse fastqc metadata
    if report_html in files:
        qc_url = files[report_html]['s3key']
    else:
        qc_url = None
    meta = parse_qc_table(filedata,
                          qc_schema=qc_schema.get('properties'),
                          url=qc_url)
    if jsondata:
        meta.update(jsondata)
    # custom fields
    if other_fields:
        for field in other_fields:
            meta.update(other_fields)
    printlog("qc meta is %s" % meta)
    # post fastq metadata
    qc_meta = ff_utils.post_metadata(meta, quality_metric, key=ff_key)
    if qc_meta.get('@graph'):
        qc_meta = qc_meta['@graph'][0]
    printlog("qc_meta is %s" % qc_meta)
    # update original file as well
    try:
        original_file = ff_utils.get_metadata(accession,
                                              key=ff_key,
                                              ff_env=tbn.env,
                                              add_on='frame=object',
                                              check_queue=True)
        printlog("original_file is %s" % original_file)
    except Exception as e:
        raise Exception("Couldn't get metadata for accession {} : ".format(accession) + str(e))
    patch_file = {'quality_metric': qc_meta['@id']}
    try:
        ff_utils.patch_metadata(patch_file, original_file['uuid'], key=ff_key)
    except Exception as e:
        raise Exception("patch_metadata failed in fastqc_updater." + str(e) +
                        "original_file ={}\n".format(str(original_file)))
    # patch the workflow run, value_qc is used to make drawing graphs easier.
    output_files = ff_meta.output_files
    output_files[0]['value_qc'] = qc_meta['@id']
    retval = {'output_files': output_files}
    printlog("retval is %s" % retval)
    return retval


def input_extra_updater(status, awsemfile, ff_meta, tbn):
    if ff_meta.awsem_app_name == 'bedGraphToBigWig':
        file_argument = 'bgfile'
        file_format = 'bw'
    elif ff_meta.awsem_app_name == 'bedtobeddb':
        file_argument = 'bedfile'
        file_format = 'beddb'
    elif ff_meta.awsem_app_name == 'bedtomultivec':
        file_argument = 'bedfile'
        file_format = 'bed.multires.mv5'
    # higlass
    if status == 'uploaded':
        if file_format == 'bw':
            higlass_uid = register_to_higlass(tbn,
                                              awsemfile.bucket,
                                              awsemfile.key,
                                              'bigwig',
                                              'vector')
        elif file_format == 'beddb':
            higlass_uid = register_to_higlass(tbn,
                                              awsemfile.bucket,
                                              awsemfile.key,
                                              'beddb',
                                              'bedlike')
        elif file_format == 'bed.multires.mv5':
            higlass_uid = register_to_higlass(tbn,
                                              awsemfile.bucket,
                                              awsemfile.key,
                                              'multivec',
                                              'multivec')
        else:
            higlass_uid = None
    # update metadata
    accession = awsemfile.runner.get_file_accessions(file_argument)[0]
    _input_extra_updater(status, tbn, accession, file_format,
                         awsemfile.md5, awsemfile.filesize, higlass_uid)
    return None


def _input_extra_updater(status, tbn, accession, extra_file_format,
                         md5=None, filesize=None, higlass_uid=None):
    try:
        original_file = ff_utils.get_metadata(accession,
                                              key=tbn.ff_keys,
                                              ff_env=tbn.env,
                                              add_on='frame=object',
                                              check_queue=True)
    except Exception as e:
        raise Exception("Can't get metadata for input file %s" % e)
    if 'extra_files' not in original_file:
        raise Exception("inconsistency - extra file metadata deleted during workflow run?")
    matching_exf_found = False
    for exf in original_file['extra_files']:
        if parse_formatstr(exf['file_format']) == extra_file_format:
            matching_exf_found = True
            exf['status'] = status
            if status == 'uploaded':
                if md5:
                    exf['md5sum'] = md5
                if filesize:
                    exf['file_size'] = filesize
    if not matching_exf_found:
        raise Exception("inconsistency - extra file metadata deleted during workflow run?")
    try:
        patch_file = {'extra_files': original_file['extra_files']}
        if higlass_uid:
            patch_file['higlass_uid'] = higlass_uid
        ff_utils.patch_metadata(patch_file, original_file['uuid'], key=tbn.ff_keys)
    except Exception as e:
        raise Exception("patch_metadata failed in extra_updater." + str(e) +
                        "original_file ={}\n".format(str(original_file)))


def get_existing_md5(file_meta):
    md5 = file_meta.get('md5sum', False)
    content_md5 = file_meta.get('content_md5sum', False)
    return md5, content_md5


def which_extra(original_file, format_if_extra=None):
    if format_if_extra:
        if 'extra_files' not in original_file:
            raise Exception("input file has no extra_files," +
                            "yet the tag 'format_if_extra' is found in the input json")
        for extra in original_file.get('extra_files'):
            if parse_formatstr(extra.get('file_format')) == format_if_extra:
                return extra
    return None


def check_mismatch(md5a, md5b):
    if md5a and md5b and md5a != md5b:
        return True
    else:
        return False


def create_patch_content_for_md5(md5, content_md5, original_md5, original_content_md5, file_size=None):
    new_content = {}

    def check_mismatch_and_update(x, original_x, fieldname):
        if check_mismatch(x, original_x):
            raise Exception(fieldname + " not matching the original one")
        if x and not original_x:
            new_content[fieldname] = x
        printlog("check_mismatch_and_update: new_content = %s" % str(new_content))
    check_mismatch_and_update(md5, original_md5, 'md5sum')
    check_mismatch_and_update(content_md5, original_content_md5, 'content_md5sum')
    if file_size:
        new_content['file_size'] = file_size
    return new_content


def create_extrafile_patch_content_for_md5(new_content, current_extra, original_file):
    current_extra = current_extra.update(new_content.copy())
    return {'extra_files': original_file.get('extra_files')}


def add_status_to_patch_content(content, current_status):
    new_file = content.copy()
    # change status to uploaded only if it is uploading or upload failed
    if current_status in ["uploading", "upload failed"]:
        new_file['status'] = 'uploaded'
    return new_file


def _md5_updater(original_file, md5, content_md5, format_if_extra=None, file_size=None):
    new_file = {}
    current_extra = which_extra(original_file, format_if_extra)
    current_status = original_file.get('status', "uploading")
    if current_extra:  # extra file
        original_md5, original_content_md5 = get_existing_md5(current_extra)
        new_content = create_patch_content_for_md5(md5, content_md5, original_md5, original_content_md5, file_size)
        if new_content:
            extra_status = current_extra.get('status', '')
            if extra_status and extra_status in ["uploading", "upload failed"]:
                new_content['status'] = 'uploaded'
            new_file = create_extrafile_patch_content_for_md5(new_content, current_extra, original_file)
    else:
        original_md5, original_content_md5 = get_existing_md5(original_file)
        new_content = create_patch_content_for_md5(md5, content_md5, original_md5, original_content_md5, file_size)
        if new_content:
            new_file = add_status_to_patch_content(new_content, current_status)
    print("new_file = %s" % str(new_file))
    return new_file


def parse_md5_report(read):
    md5_array = read.split('\n')
    if not md5_array:
        raise Exception("md5 report has no content")
    if len(md5_array) == 1:
        md5 = None
        content_md5 = md5_array[0]
    elif len(md5_array) > 1:
        md5 = md5_array[0]
        content_md5 = md5_array[1]
    return md5, content_md5


def md5_updater(status, awsemfile, ff_meta, tbn, **kwargs):
    # get key
    ff_key = tbn.ff_keys
    # get metadata about original input file
    accession = awsemfile.runner.get_file_accessions('input_file')[0]
    format_if_extras = awsemfile.runner.get_format_if_extras('input_file')
    original_file = ff_utils.get_metadata(accession,
                                          key=ff_key,
                                          ff_env=tbn.env,
                                          add_on='frame=object',
                                          check_queue=True)
    if status.lower() == 'uploaded':  # md5 report file is uploaded
        md5, content_md5 = parse_md5_report(awsemfile.read().decode('utf-8', 'backslashreplace'))
        # add file size to input file metadata
        input_file = awsemfile.runner.input_files()[0]
        file_size = boto3.client('s3').head_object(Bucket=input_file.bucket,
                                                   Key=input_file.key).get('ContentLength', '')
        for format_if_extra in format_if_extras:
            printlog("format_if_extra : %s" % format_if_extra)
            new_file = _md5_updater(original_file, md5, content_md5, format_if_extra, file_size)
            if new_file:
                break
        printlog("new_file = %s" % str(new_file))
        if new_file:
            try:
                resp = ff_utils.patch_metadata(new_file, accession, key=ff_key)
                printlog(resp)
            except Exception as e:
                # TODO specific excpetion
                # if patch fails try to patch worfklow status as failed
                raise e
    else:
        pass
    # nothing to patch to ff_meta
    return None


def find_pf(pf_meta, accession):
    for pf in pf_meta:
        if pf.accession == accession:
            return pf
    return None


def update_processed_file(awsemfile, pf_meta, tbn):
    if pf_meta:
        pf = find_pf(pf_meta, awsemfile.accession)
        if not pf:
            raise Exception("Can't find processed file with matching accession: %s" % awsemfile.accession)
        if awsemfile.is_extra:
            try:
                add_md5_filesize_to_pf_extra(pf, awsemfile)
            except Exception as e:
                raise Exception("failed to update processed file metadata %s" % e)
        else:
            try:
                add_higlass_to_pf(pf, tbn, awsemfile)
            except Exception as e:
                raise Exception("failed to regiter to higlass %s" % e)
            try:
                add_md5_filesize_to_pf(pf, awsemfile)
            except Exception as e:
                raise Exception("failed to update processed file metadata %s" % e)


def update_ffmeta_from_awsemfile(awsemfile, ff_meta, tbn, custom_qc_fields=None):
    patch_meta = False
    upload_key = awsemfile.key
    status = awsemfile.status
    printlog("awsemfile res is %s" % status)
    if status == 'COMPLETED':
        patch_meta = OUTFILE_UPDATERS[awsemfile.argument_type]('uploaded',
                                                               awsemfile,
                                                               ff_meta,
                                                               tbn,
                                                               other_fields=custom_qc_fields)
    elif status in ['FAILED']:
        patch_meta = OUTFILE_UPDATERS[awsemfile.argument_type]('upload failed',
                                                               awsemfile,
                                                               ff_meta,
                                                               tbn,
                                                               other_fields=custom_qc_fields)
        ff_meta.run_status = 'error'
        ff_meta.patch(key=tbn.ff_keys)
        raise Exception("Failed to export file %s" % (upload_key))
    return patch_meta


def update_pfmeta_from_awsemfile(awsemfile, pf_meta, tbn):
    status = awsemfile.status
    printlog("awsemfile res is %s" % status)
    if status == 'COMPLETED':
        if awsemfile.argument_type == 'Output processed file':
            update_processed_file(awsemfile, pf_meta, tbn)


def update_ffmeta(input_json):
    # check the status and other details of import
    '''
    this is to check if the task run is done:
    http://docs.sevenbridges.com/reference#get-task-execution-details
    '''
    input_json_copy = copy.deepcopy(input_json)

    # get data
    # used to automatically determine the environment
    tbn_settings = input_json_copy.get('_tibanna', {})
    try:
        tbn = TibannaSettings(tbn_settings['env'], settings=tbn_settings)
    except Exception as e:
        raise TibannaStartException("%s" % e)
    ff_meta = create_ffmeta_awsem(
        app_name=input_json_copy.get('ff_meta').get('awsem_app_name'),
        **input_json_copy.get('ff_meta')
    )

    if input_json_copy.get('error', False):
        ff_meta.run_status = 'error'
        ff_meta.description = input_json_copy.get('error')
        patch_res = ff_meta.patch(key=tbn.ff_keys)
        printlog("patch response: " + str(patch_res))
        # sending a notification email before throwing error
        if 'email' in input_json_copy['config'] and input_json_copy['config']['email']:
            try:
                send_notification_email(input_json_copy['_tibanna']['settings']['run_name'],
                                        input_json_copy['jobid'],
                                        ff_meta.run_status,
                                        input_json_copy['_tibanna']['settings']['url'])
            except Exception as e:
                printlog("Cannot send email: %s" % e)
        raise Exception(input_json_copy.get('error'))

    metadata_only = input_json_copy.get('metadata_only', False)
    if not metadata_only:
        metadata_only = input_json_copy['config'].get('runmode', {}).get('metadata_only', False)

    pf_meta = [ProcessedFileMetadata(**pf) for pf in input_json_copy.get('pf_meta')]
    custom_qc_fields = input_json_copy.get('custom_qc_fields', None)

    # ensure this bad boy is always initialized
    awsem = Awsem(input_json_copy)
    # go through this and replace awsemfile_report with awsf format
    # actually interface should be look through ff_meta files and call
    # give me the status of this thing from the runner, and runner.output_files.length
    # so we just build a runner with interface to sbg and awsem
    # runner.output_files.length()
    # runner.output_files.file.status
    # runner.output_files.file.loc
    # runner.output_files.file.get

    awsem_output = awsem.output_files()
    awsem_output_extra = awsem.secondary_output_files()
    ff_output = len(ff_meta.output_files)
    if len(awsem_output) != ff_output:
        ff_meta.run_status = 'error'
        ff_meta.description = "%d files output expected %s" % (ff_output, len(awsem_output))
        ff_meta.patch(key=tbn.ff_keys)
        raise Exception("Failing the workflow because outputed files = %d and ffmeta = %d" %
                        (awsem_output, ff_output))

    def update_metadata_from_awsemfile_list(awsemfile_list):
        patch_meta = False
        for awsemfile in awsemfile_list:
            patch_meta = update_ffmeta_from_awsemfile(awsemfile, ff_meta, tbn, custom_qc_fields)
            if not metadata_only:
                update_pfmeta_from_awsemfile(awsemfile, pf_meta, tbn)
        # allow for a simple way for updater to add appropriate meta_data
        if patch_meta:
            ff_meta.__dict__.update(patch_meta)

    update_metadata_from_awsemfile_list(awsem_output)
    update_metadata_from_awsemfile_list(awsem_output_extra)

    # if we got all the awsemfiles let's go ahead and update our ff_metadata object
    ff_meta.run_status = "complete"

    # add postrunjson log file to ff_meta as a url
    ff_meta.awsem_postrun_json = get_postrunjson_url(input_json_copy)

    # make all the file awsemfile meta-data stuff here
    # TODO: fix bugs with ff_meta mapping for output and input file
    try:
        ff_meta.patch(key=tbn.ff_keys)
    except Exception as e:
        raise Exception("Failed to update run_status %s" % str(e))
    # patch processed files - update only status, extra_files, md5sum and file_size
    if pf_meta:
        patch_fields = ['uuid', 'status', 'extra_files', 'md5sum', 'file_size', 'higlass_uid']
        try:
            for pf in pf_meta:
                printlog(pf.as_dict())
                pf.patch(key=tbn.ff_keys, fields=patch_fields)
        except Exception as e:
            raise Exception("Failed to update processed metadata %s" % str(e))

    input_json_copy['ff_meta'] = ff_meta.as_dict()
    input_json_copy['pf_meta'] = [_.as_dict() for _ in pf_meta]

    # sending a notification email after the job finishes
    if 'email' in input_json_copy['config'] and input_json_copy['config']['email']:
        try:
            send_notification_email(input_json_copy['_tibanna']['settings']['run_name'],
                                    input_json_copy['jobid'],
                                    input_json_copy['ff_meta']['run_status'],
                                    input_json_copy['_tibanna']['settings']['url'])
        except Exception as e:
            printlog("Cannot send email: %s" % e)

    return input_json_copy


def get_postrunjson_url(input_json):
    try:
        logbucket = input_json['config']['log_bucket']
        jobid = input_json['jobid']
        postrunjson_url = 'https://s3.amazonaws.com/' + logbucket + '/' + jobid + '.postrun.json'
        return postrunjson_url
    except Exception as e:
        # we don't need this for pseudo runs so just ignore
        if input_json.get('metadata_only'):
            return ''
        else:
            raise e


def send_notification_email(job_name, jobid, status, exec_url=None, sender='4dndcic@gmail.com'):
    subject = '[Tibanna] job %s : %s' % (status, job_name)
    msg = 'Job %s (%s) finished with status %s\n' % (jobid, job_name, status) \
          + 'For more detail, go to %s' % exec_url
    client = boto3.client('ses')
    client.send_email(Source=sender,
                      Destination={'ToAddresses': [sender]},
                      Message={'Subject': {'Data': subject},
                               'Body': {'Text': {'Data': msg}}})


# Cardinal knowledge of all workflow updaters
OUTFILE_UPDATERS = defaultdict(lambda: donothing)
OUTFILE_UPDATERS['Output report file'] = md5_updater
OUTFILE_UPDATERS['Output QC file'] = qc_updater
OUTFILE_UPDATERS['Output to-be-extra-input file'] = input_extra_updater
