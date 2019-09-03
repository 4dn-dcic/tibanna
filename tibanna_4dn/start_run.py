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
    WorkflowRunMetadata,
    ProcessedFileMetadata,
    WorkflowRunOutputFiles,
    merge_source_experiments,
)


class FFInput(SerializableObject):
    def __init__(self, workflow_uuid, output_bucket, jobid='', config, _tibanna=None, **kwargs):
        self.config = Config(**config)
        self.jobid = jobid

        self.input_files = kwargs.get('input_files', [])
        for infile in self.input_files:
        if not infile:
            raise("malformed input, check your input_files")

        self.workflow_uuid = workflow_uuid
        self.output_bucket = output_bucket
        self.parameters = ff_utils.convert_param(kwargs.get('parameters', {}), True)
        self.additional_benchmarking_parameters = kwargs.get('additional_benchmarking_parameters', {})
        self.tag = kwargs.get('tag', None)
        self.custom_pf_fields = kwargs.get('custom_pf_fields', None)  # custon fields for PF
        self.wfr_meta = kwargs.get('wfr_meta', None)  # custom fields for WFR
        self.output_files = kwargs.get('output_files', None)  # for user-supplied output files
        self.dependency = kwargs.get('dependency', None)
        self.wf_meta_ = None

        self.tibanna_settings = None
        if _tibanna:
            env =  _tibanna.get('env', '-'.join(self.output_bucket.split('-')[1:-1]))
            try:
                self.tibanna_settings = TibannaSettings(env, settings=_tibanna)
            except Exception as e:
                raise TibannaStartException("%s" % e)

        if not hasattr(self.config, 'overwrite_input_extra'):
            self.config.overwrite_input_extra = False
        if not config.public_postrun_json:
            config.public_postrun_json = True
        if not hasattr(config, 'email'):
            config.email = False

        @property
        def input_file_uuids(self):
            return [_['uuid'] for _ in self.input_files]

        @property
        def wf_meta(self):
            if self.wf_meta_:
                return self.wf_meta_
            try:
                self.wf_meta_ = ff_utils.get_metadata(self.workflow_uuid,
                                                      key=self.tibanna_settings.ff_keys,
                                                      ff_env=self.tibanna_settings.env,
                                                      add_on='frame=object')
                return self.wf_meta_
            except Except as e:
                raise FdnConnectionException(e)

        def update(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            

def start_run(input_json):
    '''
    this is generic function to run awsem workflow
    based on the data passed in

    workflow_uuid : for now, pass this on. Later we can add a code to automatically retrieve this from app_name.
    Note multiple workflow_uuids can be available for an app_name
    (different versions of the same app could have a different uuid)
    '''
    inp = FFInput(**input_json)
    if inp.config.log_bucket and inp.jobid:
        s3 = boto3.client('s3')
        s3.put_object(Body=json.dumps(input_json, indent=4).encode('ascii'),
                      Key=inp.jobid + '.input.json',
                      Bucket=inp.config.log_bucket)

    # input file args for awsem
    for input_file in inp.input_files:
        process_input_file_info(input_file, inp.tibanna_settings.ff_keys, inp.tibanna_settings.env, args)

    # create the ff_meta output info
    input_files_for_ffmeta = create_ffmeta_input_files_from_ff_input_file_list(inp.input_files)

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

    # 4DN dcic award and lab are used here, unless provided in wfr_meta
    ff_meta = WorkflowRunMetadata(
        workflow=inp.workflow_uuid, awsem_app_name=inp.wf_meta['app_name'], app_version=inp.wf_meta['app_version'],
        input_files=input_files_for_ffmeta,
        tag=inp.tag, run_url=inp.tibanna_settings.settings.get('url', ''),
        output_files=inp.output_files, parameters=inp.parameters,
        extra_meta=inp.wfr_meta, awsem_job_id=inp.jobid
    )

    printlog("ff_meta is %s" % ff_meta.as_dict())

    # store metadata so we know the run has started
    ff_meta.post(key=tbn.ff_keys)

    # create args
    args = dict()
    for k in ['app_name', 'app_version', 'cwl_directory_url', 'cwl_main_filename', 'cwl_child_filenames',
              'wdl_directory_url', 'wdl_main_filename', 'wdl_child_filenames']:
        printlog(inp.wf_meta.get(k))
        args[k] = inp.wf_meta.get(k, '')
    if inp.wf_meta.get('workflow_language', '') == 'WDL':
        args['language'] = 'wdl'
    else:
        # switch to v1 if available
        if 'cwl_directory_url_v1' in inp.wf_meta:  # use CWL v1
            args['cwl_directory_url'] = inp.wf_meta['cwl_directory_url_v1']
            args['cwl_version'] = 'v1'
        else:
            args['cwl_version'] = 'draft3'

    args['input_parameters'] = inp.parameters
    args['additional_benchmarking_parameters'] = inp.additional_benchmarking_parameters
    args['output_S3_bucket'] = inp.output_bucket
    args['dependency'] = inp.dependency

    # output target
    args['output_target'] = dict()
    args['secondary_output_target'] = dict()
    for of in ff_meta.output_files:
        arg_name = of.get('workflow_argument_name')
        if of.get('type') == 'Output processed file':
            args['output_target'][arg_name] = of.get('upload_key')
        elif of.get('type') == 'Output to-be-extra-input file':
            target_inf = ff_meta.input_files[0]  # assume only one input for now
            target_key = output_target_for_input_extra(target_inf, of, inp.tibanna_settings, inp.overwrite_input_extra)
            args['output_target'][arg_name] = target_key
        else:
            random_tag = str(int(random.random() * 1000000000000))
            # add a random tag at the end for non-processed file e.g. md5 report,
            # so that if two or more wfr are trigerred (e.g. one with parent file, one with extra file)
            # it will create a different output. Not implemented for processed files -
            # it's tricky because processed files must have a specific name.
            args['output_target'][arg_name] = ff_meta.uuid + '/' + arg_name + random_tag
        if 'secondary_file_formats' in of and 'extra_files' in of and of['extra_files']:
            for ext in of.get('extra_files'):
                if arg_name not in args['secondary_output_target']:
                    args['secondary_output_target'] = {arg_name: [ext.get('upload_key')]}
                else:
                    args['secondary_output_target'][arg_name].append(ext.get('upload_key'))

    inp.update(ff_meta=ff_meta.as_dict(),
               pf_meta=[meta.as_dict() for meta in pf_meta],
               args=Args(**args))
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
