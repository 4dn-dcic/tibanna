# -*- coding: utf-8 -*-
import logging
# import json
import boto3
from dcicutils import ff_utils
from core.utils import powerup
from core.utils import TibannaStartException
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

LOG = logging.getLogger(__name__)
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
    print("workflow info  %s" % wf_meta)
    LOG.info("workflow info  %s" % wf_meta)
    if 'error' in wf_meta.get('@type', []):
        raise Exception("FATAL, can't lookup workflow info for %s fourfront" % workflow_uuid)

    # get cwl info from wf_meta
    for k in ['app_name', 'app_version', 'cwl_directory_url', 'cwl_main_filename', 'cwl_child_filenames']:
        print(wf_meta.get(k))
        LOG.info(wf_meta.get(k))
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
    output_files, pf_meta = handle_processed_files(wf_meta, tibanna,
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

    print("ff_meta is %s" % ff_meta.__dict__)
    LOG.info("ff_meta is %s" % ff_meta.__dict__)

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
        if 'secondary_file_formats' in of:
            # takes only the first secondary file.
            args['secondary_output_target'][arg_name] \
                = [_.get('upload_key') for _ in of.get('extra_files', [{}, ])]

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
            infile_format = infile_meta.get('file_format')
            infile_key = inf_keys[i]
            if not fe_map:
                fe_map = FormatExtensionMap(ff_keys)
            for extra_file in infile_meta.get('extra_files'):
                extra_file_format = extra_file.get('file_format')
                extra_file_key = get_extra_file_key(infile_format, infile_key, extra_file_format, fe_map)
                extra_file_keys.append(extra_file_key)

    if len(extra_file_keys) > 0:
        if len(extra_file_keys) == 1:
            extra_file_keys = extra_file_keys[0]
        args['secondary_files'].update({input_file['workflow_argument_name']: {
                                        'bucket_name': input_file['bucket_name'],
                                        'object_key': extra_file_keys}})


def proc_file_for_arg_name(output_files, arg_name, tibanna):
    if not output_files:
        LOG.info("proc_file_for_arg_name no ouput_files specified")
        return None, None
    of = [output for output in output_files if output.get('workflow_argument_name') == arg_name]
    if of:
        if len(of) > 1:
            raise Exception("multiple output files supplied with same workflow_argument_name")
        of = of[0]
        return ProcessedFileMetadata.get(of.get('uuid'), tibanna.ff_keys,
                                         tibanna.env, return_data=True)
    else:
        LOG.info("no output_files found in input_json matching arg_name")
        LOG.info("output_files: %s" % str(output_files))
        LOG.info("arg_name: %s" % str(arg_name))
        LOG.info("tibanna is %s" % str(tibanna))
        return None, None


def handle_processed_files(wf_meta, tibanna, pf_source_experiments=None,
                           custom_fields=None, user_supplied_output_files=None):
    output_files = []
    pf_meta = []
    fe_map = None
    try:
        print("Inside handle_processed_files")
        LOG.info("Inside handle_processed_files")
        for arg in wf_meta.get('arguments', []):
            print("processing arguments %s" % str(arg))
            LOG.info("processing arguments %s" % str(arg))
            if (arg.get('argument_type') in ['Output processed file',
                                             'Output report file',
                                             'Output QC file']):
                of = dict()
                argname = of['workflow_argument_name'] = arg.get('workflow_argument_name')
                of['type'] = arg.get('argument_type')

                # see if user supplied the output file already
                # this is often the case for pseudo workflow runs (run externally)
                # TODO move this down next to post of pf
                pf, resp = proc_file_for_arg_name(user_supplied_output_files,
                                                  arg.get('workflow_argument_name'),
                                                  tibanna)
                if pf:
                    print("proc_file_for_arg_name returned %s \nfrom ff result of\n %s"
                          % (str(pf.__dict__), str(resp)))
                    LOG.info("proc_file_for_arg_name returned %s \nfrom ff result of\n %s"
                             % (str(pf.__dict__), str(resp)))
                    pf_meta.append(pf)
                else:
                    print("proc_file_for_arg_name returned %s \nfrom ff result of\n %s"
                          % (str(pf), str(resp)))
                    LOG.info("proc_file_for_arg_name returned %s \nfrom ff result of\n %s"
                             % (str(pf), str(resp)))
                if not resp:  # if it wasn't supplied as output we have to create a new one
                    assert user_supplied_output_files is None
                    if of['type'] == 'Output processed file':
                        print("creating new processedfile")
                        LOG.info("creating new processedfile")
                        if 'argument_format' not in arg:
                            raise Exception("argument format for processed file must be provided")
                        if not fe_map:
                            fe_map = FormatExtensionMap(tibanna.ff_keys)
                        # These are not processed files but report or QC files.
                        of['format'] = arg.get('argument_format')
                        if 'secondary_file_formats' in arg:
                            of['secondary_file_formats'] = arg.get('secondary_file_formats')
                            extra_files = [{"file_format": v} for v in of['secondary_file_formats']]
                        else:
                            extra_files = None
                        pf_other_fields = dict()
                        if custom_fields:
                            if argname in custom_fields:
                                pf_other_fields.update(custom_fields[argname])
                            if 'ALL' in custom_fields:
                                pf_other_fields.update(custom_fields['ALL'])
                        pf = ProcessedFileMetadata(
                            file_format=arg.get('argument_format'),
                            extra_files=extra_files,
                            source_experiments=pf_source_experiments,
                            other_fields=pf_other_fields
                        )
                        try:
                            # actually post processed file metadata here
                            resp = pf.post(key=tibanna.ff_keys)
                            resp = resp.get('@graph')[0]
                        except Exception as e:
                            LOG.error("Failed to post Processed file metadata. %s\n" % e)
                            LOG.error("resp" + str(resp) + "\n")
                            raise e
                        pf_meta.append(pf)
                if resp:
                    of['upload_key'] = resp.get('upload_key')
                    of['value'] = resp.get('uuid')
                    of['extra_files'] = resp.get('extra_files')
                output_files.append(of)

    except Exception as e:
        LOG.error("output_files = " + str(output_files) + "\n")
        LOG.error("Can't prepare output_files information. %s\n" % e)
        raise e
    return output_files, pf_meta
