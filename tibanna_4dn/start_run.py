# -*- coding: utf-8 -*-
# import json
import boto3
import json
import random
import copy
from dcicutils import ff_utils
from tibanna.utils import printlog
from .exceptions import TibannaStartException
from .pony_utils import (
    TibannaSettings,
    merge_source_experiments,
    create_ffmeta_awsem,
    ProcessedFileMetadata,
    WorkflowRunOutputFiles,
    FormatExtensionMap,
    get_extra_file_key,
    create_ffmeta_input_files_from_pony_input_file_list,
    parse_formatstr
)
from tibanna.nnested_array import (
    run_on_nested_arrays2,
    combine_two
)


def start_run(input_json):
    '''
    this is generic function to run awsem workflow
    based on the data passed in

    workflow_uuid : for now, pass this on. Later we can add a code to automatically retrieve this from app_name.
    Note multiple workflow_uuids can be available for an app_name
    (different versions of the same app could have a different uuid)
    '''
    input_json_copy = copy.deepcopy(input_json)

    # keep the input json on s3
    logbucket = input_json_copy.get('config', {}).get('log_bucket', '')
    jobid = input_json_copy.get('jobid', '')
    if logbucket and jobid:
        s3 = boto3.client('s3')
        s3.put_object(Body=json.dumps(input_json_copy, indent=4).encode('ascii'),
                      Key=jobid + '.input.json',
                      Bucket=logbucket)

    # get incomming data
    input_file_list = input_json_copy.get('input_files')
    printlog("input file list : " + str(input_file_list))
    for infile in input_file_list:
        if not infile:
            raise("malformed input, check your input_files")
    workflow_uuid = input_json_copy.get('workflow_uuid')
    output_bucket = input_json_copy.get('output_bucket')
    parameters = ff_utils.convert_param(input_json_copy.get('parameters'), True)
    tibanna_settings = input_json_copy.get('_tibanna', {})
    if 'overwrite_input_extra' in input_json_copy.get('config'):
        overwrite_input_extra = input_json_copy.get('config')['overwrite_input_extra']
    else:
        overwrite_input_extra = input_json_copy.get('overwrite_input_extra', False)
    tag = input_json_copy.get('tag')
    # if they don't pass in env guess it from output_bucket
    try:
        env = tibanna_settings.get('env', '-'.join(output_bucket.split('-')[1:-1]))
        printlog("Tibanna setting : env= " + env)
        # tibanna provides access to keys based on env and stuff like that
        tbn = TibannaSettings(env, ff_keys=input_json_copy.get('ff_keys'), settings=tibanna_settings)
    except Exception as e:
        raise TibannaStartException("%s" % e)

    args = dict()

    # get argument format & type info from workflow
    wf_meta = ff_utils.get_metadata(workflow_uuid,
                                    key=tbn.ff_keys,
                                    ff_env=tbn.env,
                                    add_on='frame=object')
    printlog("workflow info  %s" % wf_meta)
    if 'error' in wf_meta.get('@type', []):
        raise Exception("FATAL, can't lookup workflow info for %s fourfront" % workflow_uuid)

    # get cwl info from wf_meta
    for k in ['app_name', 'app_version', 'cwl_directory_url', 'cwl_main_filename', 'cwl_child_filenames',
              'wdl_directory_url', 'wdl_main_filename', 'wdl_child_filenames']:
        printlog(wf_meta.get(k))
        args[k] = wf_meta.get(k, '')
    if not args['cwl_child_filenames']:
        args['cwl_child_filenames'] = []
    if not args['wdl_child_filenames']:
        args['wdl_child_filenames'] = []

    if 'workflow_language' in wf_meta and wf_meta['workflow_language'] == 'WDL':
        args['language'] = 'wdl'
    else:
        # switch to v1 if available
        if 'cwl_directory_url_v1' in wf_meta:  # use CWL v1
            args['cwl_directory_url'] = wf_meta['cwl_directory_url_v1']
            args['cwl_version'] = 'v1'
        else:
            args['cwl_version'] = 'draft3'

    # input file args for awsem
    for input_file in input_file_list:
        process_input_file_info(input_file, tbn.ff_keys, tbn.env, args)

    # create the ff_meta output info
    input_files_for_ffmeta = create_ffmeta_input_files_from_pony_input_file_list(input_file_list)

    # source experiments
    input_file_uuids = [_['uuid'] for _ in input_file_list]
    pf_source_experiments = merge_source_experiments(input_file_uuids,
                                                     tbn.ff_keys,
                                                     tbn.env)

    # processed file metadata
    output_files, pf_meta = \
        create_wfr_output_files_and_processed_files(wf_meta, tbn,
                                                    pf_source_experiments,
                                                    custom_fields=input_json_copy.get('custom_pf_fields'),
                                                    user_supplied_output_files=input_json_copy.get('output_files'))
    print("output files= %s" % str(output_files))

    # 4DN dcic award and lab are used here, unless provided in wfr_meta
    ff_meta = create_ffmeta_awsem(
        workflow_uuid, args['app_name'], args['app_version'], input_files_for_ffmeta,
        tag=tag, run_url=tbn.settings.get('url', ''),
        output_files=output_files, parameters=parameters,
        extra_meta=input_json_copy.get('wfr_meta'), jobid=jobid
    )

    printlog("ff_meta is %s" % ff_meta.__dict__)

    # store metadata so we know the run has started
    ff_meta.post(key=tbn.ff_keys)

    # parameters
    args['input_parameters'] = input_json_copy.get('parameters')

    # output target
    args['output_target'] = dict()
    args['secondary_output_target'] = dict()
    for of in ff_meta.output_files:
        arg_name = of.get('workflow_argument_name')
        if of.get('type') == 'Output processed file':
            args['output_target'][arg_name] = of.get('upload_key')
        elif of.get('type') == 'Output to-be-extra-input file':
            target_inf = input_files_for_ffmeta[0]  # assume only one input for now
            target_key = output_target_for_input_extra(target_inf, of, tbn, overwrite_input_extra)
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

    # output bucket
    args['output_S3_bucket'] = input_json_copy.get('output_bucket')

    # dependencies
    if 'dependency' in input_json_copy:
        args['dependency'] = input_json_copy['dependency']

    # initialize config parameters as null for benchmarking
    config = input_json_copy['config']
    if 'instance_type' not in config:
        config['instance_type'] = ''
    if 'EBS_optimized' not in config:
        config['EBS_optimized'] = ''
    if 'ebs_size' not in config:
        config['ebs_size'] = 0
    if 'public_postrun_json' not in config:
        config['public_postrun_json'] = True

    input_json_copy.update({"ff_meta": ff_meta.as_dict(),
                            'pf_meta': [meta.as_dict() for meta in pf_meta],
                            "_tibanna": tbn.as_dict(),
                            "args": args})
    return(input_json_copy)


def process_input_file_info(input_file, ff_keys, ff_env, args):
    if not args or 'input_files' not in args:
        args['input_files'] = dict()
    if not args or 'secondary_files' not in args:
        args['secondary_files'] = dict()
    object_key = combine_two(input_file['uuid'], input_file['object_key'])
    args['input_files'].update({input_file['workflow_argument_name']: {
                                'bucket_name': input_file['bucket_name'],
                                'rename': input_file.get('rename', ''),
                                'object_key': object_key}})
    if input_file.get('format_if_extra', ''):
        args['input_files'][input_file['workflow_argument_name']]['format_if_extra'] \
            = input_file.get('format_if_extra')
    else:  # do not add this if the input itself is an extra file
        add_secondary_files_to_args(input_file, ff_keys, ff_env, args)


def get_extra_file_key_given_input_uuid_and_key(inf_uuid, inf_key, ff_keys, ff_env, fe_map):
    extra_file_keys = []
    not_ready_list = ['uploading', 'to be uploaded by workflow', 'upload failed', 'deleted']
    infile_meta = ff_utils.get_metadata(inf_uuid,
                                        key=ff_keys,
                                        ff_env=ff_env,
                                        add_on='frame=object')
    if infile_meta.get('extra_files'):
        infile_format = parse_formatstr(infile_meta.get('file_format'))
        for extra_file in infile_meta.get('extra_files'):
            if 'status' not in extra_file or extra_file.get('status') not in not_ready_list:
                extra_file_format = parse_formatstr(extra_file.get('file_format'))
                extra_file_key = get_extra_file_key(infile_format, inf_key, extra_file_format, fe_map)
                extra_file_keys.append(extra_file_key)
    if len(extra_file_keys) == 0:
        extra_file_keys = None
    return extra_file_keys


def add_secondary_files_to_args(input_file, ff_keys, ff_env, args):
    if not args or 'input_files' not in args:
        raise Exception("args must contain key 'input_files'")
    if 'secondary_files'not in args:
        args['secondary_files'] = dict()
    argname = input_file['workflow_argument_name']
    fe_map = FormatExtensionMap(ff_keys)
    extra_file_keys = run_on_nested_arrays2(input_file['uuid'],
                                            args['input_files'][argname]['object_key'],
                                            get_extra_file_key_given_input_uuid_and_key,
                                            ff_keys=ff_keys, ff_env=ff_env, fe_map=fe_map)
    if extra_file_keys and len(extra_file_keys) > 0:
        if len(extra_file_keys) == 1:
            extra_file_keys = extra_file_keys[0]
        args['secondary_files'].update({input_file['workflow_argument_name']: {
                                        'bucket_name': input_file['bucket_name'],
                                        'rename': input_file.get('rename', ''),
                                        'object_key': extra_file_keys}})


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


def create_wfr_outputfiles(arg, resp):
    return WorkflowRunOutputFiles(arg.get('workflow_argument_name'), arg.get('argument_type'),
                                  arg.get('argument_format', None), arg.get('secondary_file_formats', None),
                                  resp.get('upload_key', None), resp.get('uuid', None), resp.get('extra_files', None))


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
                printlog("proc_file_for_arg_name returned %s \nfrom ff result of\n %s" % (str(pf.__dict__), str(resp)))
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
            of = create_wfr_outputfiles(arg, resp)
            if pf:
                pf_meta.append(pf)
            if of:
                output_files.append(of.as_dict())
    return output_files, pf_meta


def output_target_for_input_extra(target_inf, of, tbn, overwrite_input_extra=False):
    extrafileexists = False
    printlog("target_inf = %s" % str(target_inf))  # debugging
    target_inf_meta = ff_utils.get_metadata(target_inf.get('value'),
                                            key=tbn.ff_keys,
                                            ff_env=tbn.env,
                                            add_on='frame=object',
                                            check_queue=True)
    target_format = parse_formatstr(of.get('format'))
    if target_inf_meta.get('extra_files'):
        for exf in target_inf_meta.get('extra_files'):
            if parse_formatstr(exf.get('file_format')) == target_format:
                extrafileexists = True
                if overwrite_input_extra:
                    exf['status'] = 'to be uploaded by workflow'
                break
        if not extrafileexists:
            new_extra = {'file_format': target_format, 'status': 'to be uploaded by workflow'}
            target_inf_meta['extra_files'].append(new_extra)
    else:
        new_extra = {'file_format': target_format, 'status': 'to be uploaded by workflow'}
        target_inf_meta['extra_files'] = [new_extra]
    if overwrite_input_extra or not extrafileexists:
        # first patch metadata
        printlog("extra_files_to_patch: %s" % str(target_inf_meta.get('extra_files')))  # debugging
        ff_utils.patch_metadata({'extra_files': target_inf_meta.get('extra_files')},
                                target_inf.get('value'),
                                key=tbn.ff_keys,
                                ff_env=tbn.env)
        # target key
        # NOTE : The target bucket is assume to be the same as output bucket
        # i.e. the bucket for the input file should be the same as the output bucket.
        # which is true if both input and output are processed files.
        orgfile_key = target_inf_meta.get('upload_key')
        orgfile_format = parse_formatstr(target_inf_meta.get('file_format'))
        fe_map = FormatExtensionMap(tbn.ff_keys)
        printlog("orgfile_key = %s" % orgfile_key)
        printlog("orgfile_format = %s" % orgfile_format)
        printlog("target_format = %s" % target_format)
        target_key = get_extra_file_key(orgfile_format, orgfile_key, target_format, fe_map)
        return target_key
    else:
        raise Exception("input already has extra: 'User overwrite_input_extra': true")
