# -*- coding: utf-8 -*-
from dcicutils.ff_utils import get_metadata
from tibanna.utils import _tibanna_settings, printlog
# from tibanna_4dn.vars import TIBANNA_DEFAULT_STEP_FUNCTION_NAME
from tibanna.core import run_workflow
from tibanna_4dn.exceptions import TibannaStartException, FdnConnectionException
from tibanna_4dn.pony_utils import (
    TibannaSettings,
    FormatExtensionMap,
    parse_formatstr
)
from tibanna.vars import AWS_REGION


config = {
    'function_name': 'validate_md5_s3_initiator',
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': AWS_REGION,
    'runtime': 'python3.6',
    'role': 'tibanna_lambda_init_role',
    'description': 'initiates md5/fastqc runs',
    'timeout': 300,
    'memory_size': 256
}


TIBANNA_DEFAULT_STEP_FUNCTION_NAME = 'tibanna_pony_tmp_md5'


def handler(event, context):
    '''
    this is triggered on completed file upload from s3 and
    event will be set to file data.
    '''
    # get file name
    # print(event)

    status = get_status(event)
    input_json = make_input(event)
    file_format, extra = get_file_format(event)
    if extra:  # the file is an extra file
        extra_status = get_status_for_extra_file(event, file_format)
        if status != 'to be uploaded by workflow':
            if not extra_status or extra_status != 'to be uploaded by workflow':
                input_json['input_files'][0]['format_if_extra'] = file_format
                response = run_workflow(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, input_json=input_json)
            else:
                return {'info': 'status for extra file is to be uploaded by workflow'}
        else:
            return {'info': 'parent status for extra file is to be uploaded by workflow'}
    else:
        # only run if status is uploading...
        if status == 'uploading' or event.get('force_run'):
            # trigger the step function to run
            response = run_workflow(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, input_json=input_json)
        else:
            return {'info': 'status is not uploading'}

    # run fastqc as a dependent of md5
    if file_format == 'fastq':
        md5_arn = response['_tibanna']['exec_arn']
        input_json_fastqc = make_input(event, 'fastqc-0-11-4-1', dependency=[md5_arn], run_name_prefix='fastqc')
        response_fastqc = run_workflow(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, input_json=input_json_fastqc)
        serialize_startdate(response_fastqc)
        response['fastqc'] = response_fastqc
    serialize_startdate(response)
    return response


def get_fileformats_for_accession(accession, key, env):
    try:
        meta = get_metadata(accession,
                            key=key,
                            ff_env=env,
                            add_on='frame=object',
                            check_queue=True)
    except Exception as e:
        raise FdnConnectionException("can't get metadata for the accession %s: %s" % (accession, str(e)))
    if meta:
        file_format = parse_formatstr(meta.get('file_format'))
        extra_formats = [parse_formatstr(v.get('file_format')) for v in meta.get('extra_files', [])]
        return file_format, extra_formats
    else:
        raise Exception("Can't get file format for accession %s" % accession)


def get_file_format(event):
    '''if the file extension matches the regular file format,
    returns (format, None)
    if it matches one of the format of an extra file,
    returns (format (e.g. 'pairs_px2'), 'extra')
    '''
    # guess env from bucket name
    bucket = event['Records'][0]['s3']['bucket']['name']
    env = '-'.join(bucket.split('-')[1:3])
    if env == 'fourfront-webprod':
        env = 'data'
    upload_key = event['Records'][0]['s3']['object']['key']
    uuid, object_key = upload_key.split('/')
    accession = object_key.split('.')[0]
    extension = object_key.replace(accession + '.', '')

    try:
        tbn = TibannaSettings(env=env)
    except Exception as e:
        raise TibannaStartException("%s" % e)
    file_format, extra_formats = get_fileformats_for_accession(accession, tbn.ff_keys, env)
    if file_format:
        fe_map = FormatExtensionMap(tbn.ff_keys)
        printlog(fe_map)
        if extension == fe_map.get_extension(file_format):
            return (file_format, None)
        elif extension in fe_map.get_other_extensions(file_format):
            return (file_format, None)
        else:
            for extra_format in extra_formats:
                if extension == fe_map.get_extension(extra_format):
                    return (extra_format, 'extra')
                elif extension in fe_map.get_other_extensions(extra_format):
                    return (extra_format, 'extra')
        raise Exception("file extension not matching: %s vs %s (%s)" %
                        (extension, fe_map.get_extension(file_format), file_format))
    else:
        raise Exception("Cannot get input metadata")


def get_status_for_extra_file(event, extra_format):
    if not extra_format:
        return None
    upload_key = event['Records'][0]['s3']['object']['key']
    if upload_key.endswith('html'):
        return False

    uuid, object_key = upload_key.split('/')
    accession = object_key.split('.')[0]

    # guess env from bucket name
    bucket = event['Records'][0]['s3']['bucket']['name']
    env = '-'.join(bucket.split('-')[1:3])

    try:
        tbn = TibannaSettings(env=env)
    except Exception as e:
        raise TibannaStartException("%s" % e)
    try:
        meta = get_metadata(accession,
                            key=tbn.ff_keys,
                            ff_env=env,
                            add_on='frame=object',
                            check_queue=True)
    except Exception as e:
        raise FdnConnectionException("can't get metadata for the accession %s: %s" % (accession, str(e)))
    if meta and 'extra_files' in meta:
        for exf in meta['extra_files']:
            if parse_formatstr(exf['file_format']) == extra_format:
                return exf.get('status', None)
    return None


def get_status(event):
    print("is status uploading: %s" % event)
    upload_key = event['Records'][0]['s3']['object']['key']
    if upload_key.endswith('html'):
        return False

    uuid, object_key = upload_key.split('/')
    accession = object_key.split('.')[0]

    # guess env from bucket name
    bucket = event['Records'][0]['s3']['bucket']['name']
    env = '-'.join(bucket.split('-')[1:3])

    try:
        tbn = TibannaSettings(env=env)
    except Exception as e:
        raise TibannaStartException("%s" % e)
    try:
        meta = get_metadata(accession,
                            key=tbn.ff_keys,
                            ff_env=env,
                            add_on='frame=object',
                            check_queue=True)
    except Exception as e:
        raise FdnConnectionException("can't get metadata for the accession %s: %s" % (accession, str(e)))
    if meta:
        return meta.get('status', '')
    else:
        return ''


def get_outbucket_name(bucket):
    '''chop up bucket name and have a play'''
    return bucket.replace("files", "wfoutput")


def make_input(event, wf='md5', dependency=None, run_name_prefix='validate'):
    upload_key = event['Records'][0]['s3']['object']['key']

    uuid, object_key = upload_key.split('/')

    # guess env from bucket name
    bucket = event['Records'][0]['s3']['bucket']['name']
    env = '-'.join(bucket.split('-')[1:3])

    run_name = run_name_prefix + "_%s" % (upload_key.split('/')[1].split('.')[0])
    if event.get('run_name'):
        run_name = event.get('run_name')  # used for testing

    return _make_input(env, bucket, wf, object_key, uuid, run_name, dependency)


_workflows = {'md5':
              {'uuid': 'c77a117b-9a58-477e-aaa5-291a109a99f6',
               'arg_name': 'input_file'
               },
              'fastqc-0-11-4-1':
              {'uuid': '2324ad76-ff37-4157-8bcc-3ce72b7dace9',
               'arg_name': 'input_fastq'
               },
              }


def _make_input(env, bucket, workflow, object_key, uuid, run_name, dependency=None):
    output_bucket = "elasticbeanstalk-%s-wfoutput" % env
    workflow_uuid = _workflows[workflow]['uuid']
    workflow_arg_name = _workflows[workflow]['arg_name']

    data = {"parameters": {},
            "app_name": workflow,
            "workflow_uuid": workflow_uuid,
            "input_files": [
                {"workflow_argument_name": workflow_arg_name,
                 "bucket_name": bucket,
                 "uuid": uuid,
                 "object_key": object_key,
                 }
             ],
            "output_bucket": output_bucket,
            "config": {
                "ebs_type": "io1",
                "json_bucket": "4dn-aws-pipeline-run-json",
                "ebs_iops": 500,
                "shutdown_min": 0,
                "password": "thisisnotmypassword",
                "log_bucket": "tibanna-output",
                "key_name": "4dn-encode"
              }
            }
    if dependency:
        data["dependency"] = {"exec_arn": dependency}
    data.update(_tibanna_settings({'run_id': str(object_key),
                                   'run_name': run_name,
                                   'run_type': workflow,
                                   'env': env,
                                   }))
    return data


# fix non json-serializable datetime startDate
def serialize_startdate(response):
    tibanna_resp = response.get('_tibanna', {}).get('response')
    if tibanna_resp and tibanna_resp.get('startDate'):
        tibanna_resp['startDate'] = str(tibanna_resp['startDate'])
