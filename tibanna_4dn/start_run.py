# -*- coding: utf-8 -*-
# import json
import boto3
import json
import random
import copy
from dcicutils import ff_utils
from tibanna.utils import printlog
from tibanna_ffcommon.exceptions import TibannaStartException
from tibanna_ffcommon.portal_utils import (
    TibannaSettings,
    FormatExtensionMap,
    get_extra_file_key,
    create_ffmeta_input_files_from_ff_input_file_list,
    parse_formatstr,
    process_input_file_info,
    output_target_for_input_extra
)
from .pony_utils import (
    PonyInput,
    WorkflowRunMetadata,
    ProcessedFileMetadata,
    WorkflowRunOutputFiles,
    merge_source_experiments,
)


def start_run(input_json):
    '''
    this is generic function to run awsem workflow
    based on the data passed in

    workflow_uuid : for now, pass this on. Later we can add a code to automatically retrieve this from app_name.
    Note multiple workflow_uuids can be available for an app_name
    (different versions of the same app could have a different uuid)
    '''
    inp = PonyInput(**input_json)
    if inp.config.log_bucket and inp.jobid:
        s3 = boto3.client('s3')
        s3.put_object(Body=json.dumps(input_json, indent=4).encode('ascii'),
                      Key=inp.jobid + '.input.json',
                      Bucket=inp.config.log_bucket)

    # input file args for awsem
    for input_file in inp.input_files:
        process_input_file_info(input_file, inp.tibanna_settings.ff_keys, inp.tibanna_settings.env, args)

    # source experiments
    pf_source_experiments = merge_source_experiments(inp.input_file_uuids,
                                                     inp.tibanna_settings.ff_keys,
                                                     inp.tibanna_settings.env)

    # processed file metadata
    output_files, pf_meta = \
        create_wfr_output_files_and_processed_files(inp.wf_meta, inp.tibanna_settings,
                                                    pf_source_experiments,
                                                    custom_fields=inp.custom_pf_fields,
                                                    user_supplied_output_files=inp.output_files)
    print("output files= %s" % str(output_files))

    # create the ff_meta output info
    input_files_for_ffmeta = create_ffmeta_input_files_from_ff_input_file_list(inp.input_files)
    # 4DN dcic award and lab are used here, unless provided in wfr_meta
    ff_meta = WorkflowRunMetadata(
        workflow=inp.workflow_uuid, awsem_app_name=inp.wf_meta['app_name'], app_version=inp.wf_meta['app_version'],
        input_files=input_files_for_ffmeta,
        tag=inp.tag, run_url=inp.tibanna_settings.settings.get('url', ''),
        output_files=output_files, parameters=inp.parameters,
        extra_meta=inp.wfr_meta, awsem_job_id=inp.jobid
    )
    printlog("ff_meta is %s" % ff_meta.as_dict())
    # store metadata so we know the run has started
    ff_meta.post(key=tbn.ff_keys)

    # crate args
    inp.add_args(ff_meta)

    inp.update(ff_meta=ff_meta.as_dict(),
               pf_meta=[meta.as_dict() for meta in pf_meta])
    return(inp.as_dict())


def user_supplied_proc_file(user_supplied_output_files, arg_name, tbn):
    if not user_supplied_output_files:
        raise Exception("user supplied processed files missing\n")
    of = [output for output in user_supplied_output_files if output.get('workflow_argument_name') == arg_name]
    if of:
        if len(of) > 1:
            raise Exception("multiple output files supplied with same workflow_argument_name")
        of = of[0]
        return ProcessedFileMetadata.get(of.get('uuid'), tbn.ff_keys,
                                         tbn.env, return_data=True)
    else:
        printlog("no output_files found in input_json matching arg_name")
        printlog("user_supplied_output_files: %s" % str(user_supplied_output_files))
        printlog("arg_name: %s" % str(arg_name))
        printlog("tibanna is %s" % str(tbn))
        raise Exception("user supplied processed files missing\n")


def parse_custom_fields(custom_fields, argname):
    pf_other_fields = dict()
    if custom_fields:
        if argname in custom_fields:
            pf_other_fields.update(custom_fields[argname])
        if 'ALL' in custom_fields:
            pf_other_fields.update(custom_fields['ALL'])
    if len(pf_other_fields) == 0:
        pf_other_fields = None
    return pf_other_fields


def create_and_post_processed_file(ff_keys, file_format, secondary_file_formats,
                                   source_experiments=None, other_fields=None):
    printlog(file_format)
    if not file_format:
        raise Exception("file format for processed file must be provided")
    if secondary_file_formats:
        extra_files = [{"file_format": parse_formatstr(v)} for v in secondary_file_formats]
    else:
        extra_files = None
    pf = ProcessedFileMetadata(
        file_format=file_format,
        extra_files=extra_files,
        source_experiments=source_experiments,
        other_fields=other_fields
    )
    # actually post processed file metadata here
    resp = pf.post(key=ff_keys)
    if resp and '@graph' in resp:
        resp = resp.get('@graph')[0]
    else:
        raise Exception("Failed to post Processed file metadata.\n")
    return pf, resp


def create_wfr_output_files_and_processed_files(wf_meta, tbn, pf_source_experiments=None,
                                                custom_fields=None, user_supplied_output_files=None):
    output_files = []
    pf_meta = []
    arg_type_list = ['Output processed file', 'Output report file', 'Output QC file', 'Output to-be-extra-input file']
    for arg in wf_meta.get('arguments', []):
        printlog("processing arguments %s" % str(arg))
        if arg.get('argument_type') in arg_type_list:
            if user_supplied_output_files:
                pf, resp = user_supplied_proc_file(user_supplied_output_files,
                                                   arg.get('workflow_argument_name'),
                                                   tbn)
                printlog("proc_file_for_arg_name returned %s \nfrom ff result of\n %s" % (str(pf.as_dict()), str(resp)))
            else:
                if arg.get('argument_type', '') == 'Output processed file':
                    argname = arg.get('workflow_argument_name')
                    pf, resp = create_and_post_processed_file(tbn.ff_keys,
                                                              arg.get('argument_format', ''),
                                                              arg.get('secondary_file_formats', []),
                                                              pf_source_experiments,
                                                              parse_custom_fields(custom_fields, argname))
                else:
                    pf = None
                    resp = dict()
            of = WorkflowRunOutputFiles(arg.get('workflow_argument_name'),
                                        arg.get('argument_type'),
                                        arg.get('argument_format', None),
                                        arg.get('secondary_file_formats', None),
                                        resp.get('upload_key', None),
                                        resp.get('uuid', None),
                                        resp.get('extra_files', None))
            if pf:
                pf_meta.append(pf)
            if of:
                output_files.append(of.as_dict())
    return output_files, pf_meta
