# -*- coding: utf-8 -*-
import logging
# import json
import boto3
from core import ff_utils
from core.utils import Tibanna, ensure_list

LOG = logging.getLogger(__name__)
s3 = boto3.resource('s3')


def handler(event, context):
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
    tibanna_settings = event.get('_tibanna', {})
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

    # get format-extension map
    try:
        fp_schema = ff_utils.get_metadata("profiles/file_processed.json", key=tibanna.ff_keys)
        fe_map = fp_schema.get('file_format_file_extension')
    except Exception as e:
        LOG.error("Can't get format-extension map from file_processed schema. %s\n" % e)

    # processed file metadata
    output_files = []
    try:
        if 'arguments' in workflow_info:
            pf_meta = []
            for arg in workflow_info.get('arguments'):
                if (arg.get('argument_type') in
                   ['Output processed file', 'Output report file', 'Output QC file']):

                    of = dict()
                    of['workflow_argument_name'] = arg.get('workflow_argument_name')
                    of['type'] = arg.get('argument_type')
                    if 'argument_format' in arg:
                        # These are not processed files but report or QC files.
                        pf = ff_utils.ProcessedFileMetadata(file_format=arg.get('argument_format'))
                        try:
                            resp = pf.post(key=tibanna.ff_keys)  # actually post processed file metadata here
                            resp = resp.get('@graph')[0]
                            of['upload_key'] = resp.get('upload_key')
                            of['value'] = resp.get('uuid')
                        except Exception as e:
                            LOG.error("Failed to post Processed file metadata. %s\n" % e)
                            LOG.error("resp" + str(resp) + "\n")
                            raise e
                        of['format'] = arg.get('argument_format')
                        of['extension'] = fe_map.get(arg.get('argument_format'))
                        pf_meta.append(pf)
                    output_files.append(of)

    except Exception as e:
        LOG.error("output_files = " + str(output_files) + "\n")
        LOG.error("Can't prepare output_files information. %s\n" % e)
        raise e

    # create the ff_meta output info
    input_files = []
    for input_file in input_file_list:
        for idx, uuid in enumerate(ensure_list(input_file['uuid'])):
            input_files.append({'workflow_argument_name': input_file['workflow_argument_name'],
                                'value': uuid, 'ordinal': idx + 1})
    LOG.info("input_files is %s" % input_files)

    ff_meta = ff_utils.create_ffmeta_awsem(workflow_uuid, app_name, input_files,
                                           run_url=tibanna.settings.get('url', ''),
                                           output_files=output_files)

    LOG.info("ff_meta is %s" % ff_meta.__dict__)

    # store metadata so we know the run has started
    ff_meta.post_plain_wrf(key=tibanna.ff_keys)

    # input file args for awsem
    args['input_files'] = dict()
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

    LOG.info("input_file_args is %s" % args['input_files'])
    args['secondary_files'] = dict()   # temporary, later fill in based on the attachment information

    # parameters
    args['input_parameters'] = event.get('parameters')

    # output target
    args['output_target'] = dict()
    for of in ff_meta.output_files:
        arg_name = of.get('workflow_argument_name')
        if of.get('type') == 'Output processed file':
            args['output_target'][arg_name] = of.get('upload_key')
        else:
            args['output_target'][arg_name] = ff_meta.uuid + '/' + arg_name

    # output bucket
    args['output_S3_bucket'] = event.get('output_bucket')

    event.update({"ff_meta": ff_meta.as_dict(),
                  'pf_meta': [meta.as_dict() for meta in pf_meta],
                  "_tibanna": tibanna.as_dict(),
                  "args": args
                  })
    return(event)

    # let's not pass keys in plain text parameters
    # return {"input_file_args": input_file_list,
    #        "ff_meta": ff_meta.as_dict(),
    #        'pf_meta': [meta.as_dict() for meta in pf_meta],
    #        "_tibanna": tibanna.as_dict(),
    #        "config": event.get("config"),
    #        "args": args,
    #        "workflow_uuid": workflow_uuid,
    #        "app_name": app_name
    #        }
