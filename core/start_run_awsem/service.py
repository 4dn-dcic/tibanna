# -*- coding: utf-8 -*-
import logging
# import json
import boto3
from core import ff_utils
from core.utils import Tibanna, ensure_list, powerup

LOG = logging.getLogger(__name__)
s3 = boto3.resource('s3')


def metadata_only(event):
    # this relies on the fact that event contains and output key with output files
    assert event['metadata_only']
    assert event['output_files']
    return real_handler(event, None)


@powerup('start_run_awsem', metadata_only)
def handler(event, context):
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
    app_name = event.get('app_name')
    print(app_name)
    workflow_uuid = event.get('workflow_uuid')
    output_bucket = event.get('output_bucket')
    parameters = ff_utils.convert_param(event.get('parameters'), True)
    tibanna_settings = event.get('_tibanna', {})
    tag = event.get('tag')
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env', '-'.join(output_bucket.split('-')[1:-1]))
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, s3_keys=event.get('s3_keys'), ff_keys=event.get('ff_keys'),
                      settings=tibanna_settings)

    args = dict()

    # get argument format & type info from workflow
    workflow_info = ff_utils.get_metadata(workflow_uuid, key=tibanna.ff_keys)
    LOG.info("workflow info  %s" % workflow_info)
    if 'error' in workflow_info.get('@type', []):
        raise Exception("FATAL, can't lookup workflow info for % fourfront" % workflow_uuid)

    # get cwl info from workflow_info
    for k in ['app_name', 'app_version', 'cwl_directory_url', 'cwl_main_filename', 'cwl_child_filenames']:
        LOG.info(workflow_info.get(k))
        args[k] = workflow_info.get(k)

    # create the ff_meta output info
    input_files = []
    for input_file in input_file_list:
        for idx, uuid in enumerate(ensure_list(input_file['uuid'])):
            input_files.append({'workflow_argument_name': input_file['workflow_argument_name'],
                                'value': uuid, 'ordinal': idx + 1})
    LOG.info("input_files is %s" % input_files)

    # input file args for awsem
    args['input_files'] = dict()
    args['secondary_files'] = dict()
    fe_map = get_format_extension_map(tibanna)
    pf_source_experiments_dict = dict()
    for input_file in input_file_list:
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

        if isinstance(input_file['uuid'], list):
            inf_uuids = input_file['uuid']
        else:
            inf_uuids = [input_file['uuid']]
        for inf_uuid in inf_uuids:
            infile_meta = ff_utils.get_metadata(inf_uuid, key=tibanna.ff_keys)
            if infile_meta.get('experiments'):
                for exp in infile_meta.get('experiments'):
                    exp_uuid = ff_utils.get_metadata(exp, key=tibanna.ff_keys).get('uuid')
                    pf_source_experiments_dict.update({exp_uuid: 1})
            if infile_meta.get('source_experiments'):
                pf_source_experiments_dict.update({_: 1 for _ in infile_meta.get('source_experiments')})
            if infile_meta.get('extra_files'):
                extra_file_format = infile_meta.get('extra_files')[0].get('file_format')  # only the first extra file
                extra_file_extension = fe_map.get(extra_file_format)
                infile_format = infile_meta.get('file_format')
                infile_extension = fe_map.get(infile_format)
                extra_file_key = object_key.replace(infile_extension, extra_file_extension)
                if input_file['workflow_argument_name'] in args['secondary_files']:
                    if isinstance(args['secondary_files']['object_key'], list):
                        args['secondary_files']['object_key'].add(extra_file_key)
                    else:
                        existing_extra_file_key = args['secondary_files']['object_key']
                        args['secondary_files']['object_key'] = [existing_extra_file_key, extra_file_key]
                else:
                    args['secondary_files'].update({input_file['workflow_argument_name']: {
                                                    'bucket_name': input_file['bucket_name'],
                                                    'object_key': extra_file_key}})

    # processed file metadata
    output_files, pf_meta = handle_processed_files(workflow_info, tibanna,
                                                   pf_source_experiments_dict.keys(),
                                                   user_supplied_output_files=event.get('output_files'))

    ff_meta = ff_utils.create_ffmeta_awsem(workflow_uuid, app_name, input_files, tag=tag,
                                           run_url=tibanna.settings.get('url', ''),
                                           output_files=output_files, parameters=parameters,
                                           alias=event.get('wfr_alias'))

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
            args['output_target'][arg_name] = ff_meta.uuid + '/' + arg_name
        if 'secondary_file_formats' in of:
            # takes only the first secondary file.
            args['secondary_output_target'][arg_name] \
                = of.get('extra_files', [{}, ])[0].get('upload_key')

    # output bucket
    args['output_S3_bucket'] = event.get('output_bucket')

    if 'instance_type' not in event['config']:
        event['config']['instance_type'] = ''
    if 'EBS_optimized' not in event['config']:
        event['config']['EBS_optimized'] = ''
    if 'ebs_size' not in event['config']:
        event['config']['ebs_size'] = 0

    event.update({"ff_meta": ff_meta.as_dict(),
                  'pf_meta': [meta.as_dict() for meta in pf_meta],
                  "_tibanna": tibanna.as_dict(),
                  "args": args
                  })
    return(event)


def get_format_extension_map(tibanna):
    # get format-extension map
    try:
        fp_schema = ff_utils.get_metadata("profiles/file_processed.json", key=tibanna.ff_keys)
        fe_map = fp_schema.get('file_format_file_extension')
    except Exception as e:
        LOG.error("Can't get format-extension map from file_processed schema. %s\n" % e)

    return fe_map


def proc_file_for_arg_name(output_files, arg_name, tibanna):
    if not output_files:
        LOG.info("proc_file_for_arg_name no ouput_files specified")
        return None, None
    of = [output for output in output_files if output.get('workflow_argument_name') == arg_name]
    if of:
        if len(of) > 1:
            raise Exception("multiple output files supplied with same workflow_argument_name")
        of = of[0]
        return ff_utils.ProcessedFileMetadata.get(of.get('uuid'), tibanna.ff_keys, return_data=True)
    else:
        LOG.info("no output_files found in input_json matching arg_name")
        LOG.info("output_files: %s" % str(output_files))
        LOG.info("arg_name: %s" % str(arg_name))
        LOG.info("tibanna is %s" % str(tibanna))
        return None, None


def handle_processed_files(workflow_info, tibanna, pf_source_experiments=None,
                           user_supplied_output_files=None):

    fe_map = get_format_extension_map(tibanna)
    output_files = []
    pf_meta = []
    try:
        for arg in workflow_info.get('arguments', []):
            if (arg.get('argument_type') in ['Output processed file',
                                             'Output report file',
                                             'Output QC file']):

                of = dict()
                of['workflow_argument_name'] = arg.get('workflow_argument_name')
                of['type'] = arg.get('argument_type')
                if 'argument_format' in arg:
                    # These are not processed files but report or QC files.
                    if 'secondary_file_formats' in arg:
                        of['secondary_file_formats'] = arg.get('secondary_file_formats')
                        of['secondary_file_extensions'] = [fe_map.get(v) for v in arg.get('secondary_file_formats')]
                        extra_files = [{"file_format": v} for v in of['secondary_file_formats']]
                    else:
                        extra_files = None

                    # see if user supplied the output file already
                    # this is often the case for pseudo workflow runs (run externally)
                    # TODO move this down next to post of pf
                    pf, resp = proc_file_for_arg_name(user_supplied_output_files,
                                                      arg.get('workflow_argument_name'),
                                                      tibanna)
                    if pf:
                        LOG.info("proc_file_for_arg_name returned %s \nfrom ff result of\n %s"
                                 % (str(pf.__dict__), str(resp)))
                    else:
                        LOG.info("proc_file_for_arg_name returned %s \nfrom ff result of\n %s"
                                 % (str(pf), str(resp)))

                    # if it wasn't supplied as output we have to create a new one
                    if not resp:
                        LOG.info("creating new processedfile")
                        assert user_supplied_output_files is None
                        pf = ff_utils.ProcessedFileMetadata(file_format=arg.get('argument_format'),
                                                            extra_files=extra_files,
                                                            source_experiments=pf_source_experiments)
                        try:
                            # actually post processed file metadata here
                            resp = pf.post(key=tibanna.ff_keys)
                            resp = resp.get('@graph')[0]

                        except Exception as e:
                            LOG.error("Failed to post Processed file metadata. %s\n" % e)
                            LOG.error("resp" + str(resp) + "\n")
                            raise e
                    of['upload_key'] = resp.get('upload_key')
                    of['value'] = resp.get('uuid')
                    of['extra_files'] = resp.get('extra_files')
                    of['format'] = arg.get('argument_format')
                    of['extension'] = fe_map.get(arg.get('argument_format'))
                    pf_meta.append(pf)
                output_files.append(of)

    except Exception as e:
        LOG.error("output_files = " + str(output_files) + "\n")
        LOG.error("Can't prepare output_files information. %s\n" % e)
        raise e
    return output_files, pf_meta
