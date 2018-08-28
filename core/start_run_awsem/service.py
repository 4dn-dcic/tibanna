# -*- coding: utf-8 -*-
# import json
import boto3
from dcicutils import ff_utils
from core.utils import powerup
from core.utils import TibannaStartException
from core.utils import printlog
from core.pony_utils import (
    Tibanna,
    merge_source_experiments,
    create_ffmeta_awsem,
    aslist,
    ProcessedFileMetadata,
    FormatExtensionMap,
    get_extra_file_key,
    create_ffmeta_input_files_from_pony_input_file_list
)
import random

s3 = boto3.resource('s3')


def metadata_only(event):
    # this relies on the fact that event contains and output key with output files
    assert event['metadata_only']
    assert event['output_files']
    return real_handler(event, None)


@powerup('start_run_awsem', metadata_only)
def handler(event, context):
    if event.get('push_error_to_end', True):
        event['push_error_to_end'] = True  # push error to end by default for pony
    return real_handler(event, context)


def real_handler(event, context):
    '''
    this is generic function to run awsem workflow
    based on the data passed in

    workflow_uuid : for now, pass this on. Later we can add a code to automatically retrieve this from app_name.
    Note multiple workflow_uuids can be available for an app_name
    (different versions of the same app could have a different uuid)
    '''
    # get incomming data
    input_file_list = event.get('input_files')
    for infile in input_file_list:
        if not infile:
            raise("malformed input, check your input_files")
    app_name = event.get('app_name')
    print(app_name)
    workflow_uuid = event.get('workflow_uuid')
    output_bucket = event.get('output_bucket')
    parameters = ff_utils.convert_param(event.get('parameters'), True)
    tibanna_settings = event.get('_tibanna', {})
    tag = event.get('tag')
    # if they don't pass in env guess it from output_bucket
    try:
        env = tibanna_settings.get('env', '-'.join(output_bucket.split('-')[1:-1]))
        # tibanna provides access to keys based on env and stuff like that
        tibanna = Tibanna(env, ff_keys=event.get('ff_keys'), settings=tibanna_settings)
    except Exception as e:
        raise TibannaStartException("%s" % e)

    args = dict()

    # get argument format & type info from workflow
    wf_meta = ff_utils.get_metadata(workflow_uuid,
                                    key=tibanna.ff_keys,
                                    ff_env=tibanna.env,
                                    add_on='frame=object')
    printlog("workflow info  %s" % wf_meta)
    if 'error' in wf_meta.get('@type', []):
        raise Exception("FATAL, can't lookup workflow info for %s fourfront" % workflow_uuid)

    # get cwl info from wf_meta
    for k in ['app_name', 'app_version', 'cwl_directory_url', 'cwl_main_filename', 'cwl_child_filenames']:
        printlog(wf_meta.get(k))
        args[k] = wf_meta.get(k)
    if not args['cwl_child_filenames']:
        args['cwl_child_filenames'] = []

    # switch to v1 if available
    if 'cwl_directory_url_v1' in wf_meta:  # use CWL v1
        args['cwl_directory_url'] = wf_meta['cwl_directory_url_v1']
        args['cwl_version'] = 'v1'
    else:
        args['cwl_version'] = 'draft3'

    # input file args for awsem
    for input_file in input_file_list:
        process_input_file_info(input_file, tibanna.ff_keys, tibanna.env, args)

    # create the ff_meta output info
    input_files_for_ffmeta = create_ffmeta_input_files_from_pony_input_file_list(input_file_list)

    # source experiments
    input_file_uuids = [_['uuid'] for _ in input_file_list]
    pf_source_experiments = merge_source_experiments(input_file_uuids,
                                                     tibanna.ff_keys,
                                                     tibanna.env)

    # processed file metadata
    output_files, pf_meta = \
        create_wfr_output_files_and_processed_files(wf_meta, tibanna,
                                                    pf_source_experiments,
                                                    custom_fields=event.get('custom_pf_fields'),
                                                    user_supplied_output_files=event.get('output_files'))
    print("output files= %s" % str(output_files))

    # 4DN dcic award and lab are used here, unless provided in wfr_meta
    ff_meta = create_ffmeta_awsem(
        workflow_uuid, app_name, input_files_for_ffmeta, tag=tag,
        run_url=tibanna.settings.get('url', ''),
        output_files=output_files, parameters=parameters,
        extra_meta=event.get('wfr_meta'),
    )

    printlog("ff_meta is %s" % ff_meta.__dict__)

    # store metadata so we know the run has started
    ff_meta.post(key=tibanna.ff_keys)

    # parameters
    args['input_parameters'] = event.get('parameters')

    # output target
    args['output_target'] = dict()
    args['secondary_output_target'] = dict()
    for of in ff_meta.output_files:
        arg_name = of.get('workflow_argument_name')
        if of.get('type') == 'Output processed file':
            args['output_target'][arg_name] = of.get('upload_key')
        else:
            random_tag = str(int(random.random() * 1000000000000))
            # add a random tag at the end for non-processed file e.g. md5 report,
            # so that if two or more wfr are trigerred (e.g. one with parent file, one with extra file)
            # it will create a different output. Not implemented for processed files -
            # it's tricky because processed files must have a specific name.
            args['output_target'][arg_name] = ff_meta.uuid + '/' + arg_name + random_tag
        if 'secondary_file_formats' in of and 'extra_files' in of and of['extra_files']:
            for ext in of.get('extra_files'):
                args['secondary_output_target'][arg_name].append(ext.get('upload_key'))

    # output bucket
    args['output_S3_bucket'] = event.get('output_bucket')

    # dependencies
    if 'dependency' in event:
        args['dependency'] = event['dependency']

    # initialize config parameters as null for benchmarking
    config = event['config']
    if 'instance_type' not in config:
        config['instance_type'] = ''
    if 'EBS_optimized' not in config:
        config['EBS_optimized'] = ''
    if 'ebs_size' not in config:
        config['ebs_size'] = 0
    if 'public_postrun_json' not in config:
        config['public_postrun_json'] = True

    event.update({"ff_meta": ff_meta.as_dict(),
                  'pf_meta': [meta.as_dict() for meta in pf_meta],
                  "_tibanna": tibanna.as_dict(),
                  "args": args
                  })
    return(event)


def process_input_file_info(input_file, ff_keys, ff_env, args):
    if not args or 'input_files' not in args:
        args['input_files'] = dict()
    if not args or 'secondary_files' not in args:
        args['secondary_files'] = dict()
    if isinstance(input_file['uuid'], unicode):
        input_file['uuid'] = input_file['uuid'].encode('utf-8')
    if isinstance(input_file['object_key'], unicode):
        input_file['object_key'] = input_file['object_key'].encode('utf-8')
    if isinstance(input_file['uuid'], str) and isinstance(input_file['object_key'], str):
        object_key = input_file['uuid'] + '/' + input_file['object_key']
    elif (isinstance(input_file['uuid'], list) and
          isinstance(input_file['object_key'], list) and
          len(input_file['uuid']) == len(input_file['object_key'])):

        object_key = [a + '/' + b for a, b in zip(input_file['uuid'], input_file['object_key'])]
    else:
        raise Exception("input_file uuid and object_key should match in their type and length (if lists) : " +
                        "type{}{} length{}{}".format(type(input_file['uuid']), type(input_file['object_key']),
                                                     len(input_file['uuid']), len(input_file['object_key'])))
    args['input_files'].update({input_file['workflow_argument_name']: {
                                'bucket_name': input_file['bucket_name'],
                                'object_key': object_key}})
    if input_file.get('format_if_extra', ''):
        args['input_files'][input_file['workflow_argument_name']]['format_if_extra'] \
            = input_file.get('format_if_extra')
    else:  # do not add this if the input itself is an extra file
        add_secondary_files_to_args(input_file, ff_keys, ff_env, args)


def parse_formatstr(file_format_str):
    return file_format_str.replace('/file-formats/', '').replace('/', '')


def add_secondary_files_to_args(input_file, ff_keys, ff_env, args):
    if not args or 'input_files' not in args:
        raise Exception("args must contain key 'input_files'")
    if 'secondary_files'not in args:
        args['secondary_files'] = dict()
    inf_uuids = aslist(input_file['uuid'])
    argname = input_file['workflow_argument_name']
    extra_file_keys = []
    inf_object_key = args['input_files'][argname]['object_key']
    inf_keys = aslist(inf_object_key)
    fe_map = None
    for i, inf_uuid in enumerate(inf_uuids):
        infile_meta = ff_utils.get_metadata(inf_uuid,
                                            key=ff_keys,
                                            ff_env=ff_env,
                                            add_on='frame=object')
        if infile_meta.get('extra_files'):
            infile_format = parse_formatstr(infile_meta.get('file_format'))
            infile_key = inf_keys[i]
            if not fe_map:
                fe_map = FormatExtensionMap(ff_keys)
            for extra_file in infile_meta.get('extra_files'):
                extra_file_format = parse_formatstr(extra_file.get('file_format'))
                extra_file_key = get_extra_file_key(infile_format, infile_key, extra_file_format, fe_map)
                extra_file_keys.append(extra_file_key)

    if len(extra_file_keys) > 0:
        if len(extra_file_keys) == 1:
            extra_file_keys = extra_file_keys[0]
        args['secondary_files'].update({input_file['workflow_argument_name']: {
                                        'bucket_name': input_file['bucket_name'],
                                        'object_key': extra_file_keys}})


def user_supplied_proc_file(user_supplied_output_files, arg_name, tibanna):
    if not user_supplied_output_files:
        raise Exception("user supplied processed files missing\n")
    of = [output for output in user_supplied_output_files if output.get('workflow_argument_name') == arg_name]
    if of:
        if len(of) > 1:
            raise Exception("multiple output files supplied with same workflow_argument_name")
        of = of[0]
        return ProcessedFileMetadata.get(of.get('uuid'), tibanna.ff_keys,
                                         tibanna.env, return_data=True)
    else:
        printlog("no output_files found in input_json matching arg_name")
        printlog("user_supplied_output_files: %s" % str(user_supplied_output_files))
        printlog("arg_name: %s" % str(arg_name))
        printlog("tibanna is %s" % str(tibanna))
        raise Exception("user supplied processed files missing\n")


class WorkflowRunOutputFiles(object):
    def __init__(self, workflow_argument_name, argument_type, file_format=None, secondary_file_formats=None,
                 upload_key=None, uuid=None, extra_files=None):
        self.workflow_argument_name = workflow_argument_name
        self.type = argument_type
        self.format = file_format
        self.secondary_file_formats = secondary_file_formats
        self.value = uuid
        self.upload_key = upload_key
        self.extra_files = extra_files

    def as_dict(self):
        return self.__dict__


def parse_custom_fields(custom_fields, argname):
    pf_other_fields = dict()
    if custom_fields:
        if argname in custom_fields:
            pf_other_fields.update(custom_fields[argname])
        if 'ALL' in custom_fields:
            pf_other_fields.update(custom_fields['ALL'])
    return pf_other_fields


def create_and_post_processed_file(ff_keys, file_format, secondary_file_formats,
                                   source_experiments=None, other_fields=None):
    if not file_format:
        raise Exception("file format for processed file must be provided")
    extra_files = [{"file_format": v} for v in secondary_file_formats]
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


def create_wfr_output_files_and_processed_files(wf_meta, tibanna, pf_source_experiments=None,
                                                custom_fields=None, user_supplied_output_files=None):
    output_files = []
    pf_meta = []
    arg_type_list = ['Output processed file', 'Output report file', 'Output QC file']
    for arg in wf_meta.get('arguments', []):
        printlog("processing arguments %s" % str(arg))
        if arg.get('argument_type') in arg_type_list:
            if user_supplied_output_files:
                pf, resp = user_supplied_proc_file(user_supplied_output_files,
                                                   arg.get('workflow_argument_name'),
                                                   tibanna)
                printlog("proc_file_for_arg_name returned %s \nfrom ff result of\n %s" % (str(pf.__dict__), str(resp)))
            else:
                if arg.get('argument_type', '') == 'Output processed file':
                    argname = arg.get('workflow_argument_name')
                    pf, resp = create_and_post_processed_file(tibanna.ff_keys,
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
