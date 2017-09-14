# -*- coding: utf-8 -*-
import logging
# import json
import boto3
from core import ff_utils
from core.utils import Tibanna, ensure_list, s3Utils
from Benchmark import Benchmark as B
import copy

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
    parameters = ff_utils.convert_param(event.get('parameters'), True)
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

    # processed file metadata
    output_files, pf_meta = handle_processed_files(workflow_info, tibanna)

    # create the ff_meta output info
    input_files = []
    for input_file in input_file_list:
        for idx, uuid in enumerate(ensure_list(input_file['uuid'])):
            input_files.append({'workflow_argument_name': input_file['workflow_argument_name'],
                                'value': uuid, 'ordinal': idx + 1})
    LOG.info("input_files is %s" % input_files)

    ff_meta = ff_utils.create_ffmeta_awsem(workflow_uuid, app_name, input_files,
                                           run_url=tibanna.settings.get('url', ''),
                                           output_files=output_files, parameters=parameters)

    LOG.info("ff_meta is %s" % ff_meta.__dict__)

    # store metadata so we know the run has started
    ff_meta.post(key=tibanna.ff_keys)

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

    event['config'] = update_config(event.get('config'), event.get('app_name'),
                                    event.get('input_files'), event.get('parameters'))

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


def handle_processed_files(workflow_info, tibanna):

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
                    pf = ff_utils.ProcessedFileMetadata(file_format=arg.get('argument_format'),
                                                        extra_files=extra_files)
                    try:
                        resp = pf.post(key=tibanna.ff_keys)  # actually post processed file metadata here
                        resp = resp.get('@graph')[0]
                        of['upload_key'] = resp.get('upload_key')
                        of['value'] = resp.get('uuid')
                        of['extra_files'] = resp.get('extra_files')
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
    return output_files, pf_meta


def update_config(old_config, app_name, input_files, parameters):

    config = copy.deepcopy(old_config)
    if 'instance_type' in old_config and 'ebs_size' in old_config and 'EBS_optimized' in old_config:
        pass
    else:
        input_size_in_bytes = dict()
        try:
            for f in input_files:
                argname = f['workflow_argument_name']
                bucket = f['bucket_name']
                s3 = s3Utils(bucket, bucket, bucket)
                if isinstance(f['uuid']) and isinstance(f['object_key']):
                    size = []
                    for u, k in zip(f['uuid'], f['object_key']):
                        key = u + '/' + k
                        size.append(s3.get_file_size(key, bucket))
                else:
                    key = f['uuid'] + '/' + f['object_key']
                    size = s3.get_file_size(key, bucket)
                input_size_in_bytes.update({str(argname): size})
        except:
            raise Exception("Can't get input file size")

        print(input_size_in_bytes)
        res = B.benchmark(app_name, {'input_size_in_bytes': input_size_in_bytes, 'parameters': parameters})
        print(res)
        if res is not None:
            instance_type = res['aws']['recommended_instance_type']
            ebs_size = 10 if res['total_size_in_GB'] < 10 else int(res['total_size_in_GB']) + 1
            ebs_opt = res['aws']['EBS_optimized']

            if 'instance_type' not in old_config:
                config['instance_type'] = instance_type
                config['ebs_size'] = ebs_size
                config['EBS_optimized'] = ebs_opt

        elif 'instance_type' not in old_config:
            raise Exception("instance type cannot be determined nor given")
        elif 'ebs_size' not in old_config:
            raise Exception("ebs_size cannot be determined nor given")
        elif 'EBS_optimized' not in old_config:
            raise Exception("EBS_optimized cannot be determined nor given")

    return(config)
