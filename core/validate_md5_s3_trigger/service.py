# -*- coding: utf-8 -*-
from core.utils import _tibanna_settings
from core.utils import TIBANNA_DEFAULT_STEP_FUNCTION_NAME
from core.utils import run_workflow
from core.pony_utils import Tibanna, FormatExtensionMap
from dcicutils.ff_utils import get_metadata


def handler(event, context):
    '''
    this is triggered on completed file upload from s3 and
    event will be set to file data.
    '''
    # get file name
    # print(event)

    input_json = make_input(event)
    print('EVENT: %s' % event)
    extra_file_format = get_extra_file_format(event)
    status = get_status(event)
    if extra_file_format:
        if status != 'to be uploaded by workflow':
            # for extra file-triggered md5 run, status check is skipped.
            input_json['input_files'][0]['format_if_extra'] = extra_file_format
            response = run_workflow(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, input_json=input_json)
    else:
        # only run if status is uploading...
        if status == 'uploading' or event.get('force_run'):
            # trigger the step function to run
            response = run_workflow(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, input_json=input_json)
        else:
            return {'info': 'status is not uploading'}

    # fix non json-serializable datetime startDate
    print('RESPONSE: %s' % response)
    if response.get('startDate'):
        response['startDate'] = str(response['startDate'])
    return response


def get_extra_file_format(event):
    '''if the file extension matches the regular file format,
    returns None
    if it matches one of the format of an extra file,
    returns that format (e.g. 'pairs_px2'
    '''
    # guess env from bucket name
    bucket = event['Records'][0]['s3']['bucket']['name']
    env = '-'.join(bucket.split('-')[1:3])
    # env will always be fourfront-webprod, since it is using file bucket name
    upload_key = event['Records'][0]['s3']['object']['key']
    uuid, object_key = upload_key.split('/')
    accession = object_key.split('.')[0]
    extension = object_key.replace(accession + '.', '')

    tibanna = Tibanna(env=env)
    meta = get_metadata(accession,
                        key=tibanna.ff_keys,
                        ff_env=env,
                        add_on='frame=object',
                        check_queue=True)
    if meta:
        file_format = meta.get('file_format')
        fe_map = FormatExtensionMap(tibanna.ff_keys)
        print('FE_MAP: %s' % fe_map.fe_dict)
        if extension == fe_map.get_extension(file_format):
            return None
        elif extension in fe_map.get_other_extensions(file_format):
            return None
        else:
            for extra in meta.get('extra_files', []):
                extra_format = extra.get('file_format')
                if extension == fe_map.get_extension(extra_format):
                    return extra_format
                elif extension in fe_map.get_other_extensions(extra_format):
                    return extra_format
        raise Exception("file extension not matching: %s vs %s (%s)" %
                        (extension, fe_map.get_extension(file_format), file_format))
    else:
        raise Exception("Cannot get input metadata")


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

    tibanna = Tibanna(env=env)
    meta = get_metadata(accession,
                        key=tibanna.ff_keys,
                        ff_env=env,
                        add_on='frame=object',
                        check_queue=True)
    if meta:
        return meta.get('status', '')
    else:
        return ''


def get_outbucket_name(bucket):
    '''chop up bucket name and have a play'''
    return bucket.replace("files", "wfoutput")


def make_input(event):
    upload_key = event['Records'][0]['s3']['object']['key']

    uuid, object_key = upload_key.split('/')

    # guess env from bucket name
    bucket = event['Records'][0]['s3']['bucket']['name']
    env = '-'.join(bucket.split('-')[1:3])

    run_name = "validate_%s" % (upload_key.split('/')[1].split('.')[0])
    if event.get('run_name'):
        run_name = event.get('run_name')  # used for testing

    return _make_input(env, bucket, 'md5', object_key, uuid, run_name)


_workflows = {'md5':
              {'uuid': 'c77a117b-9a58-477e-aaa5-291a109a99f6',
               'arg_name': 'input_file'
               },
              'fastqc-0-11-4-1':
              {'uuid': '2324ad76-ff37-4157-8bcc-3ce72b7dace9',
               'arg_name': 'input_fastq'
               },
              }


def _make_input(env, bucket, workflow, object_key, uuid, run_name):
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
                "shutdown_min": 30,
                "password": "thisisnotmypassword",
                "log_bucket": "tibanna-output",
                "key_name": ""
              },
            }
    data.update(_tibanna_settings({'run_id': str(object_key),
                                   'run_name': run_name,
                                   'run_type': workflow,
                                   'env': env,
                                   }))
    return data
