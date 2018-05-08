from __future__ import print_function
import json
import boto3
import os
import mimetypes
from zipfile import ZipFile
from io import BytesIO
from uuid import uuid4
from .ff_utils import get_metadata
import logging


###########################
# Config
###########################
s3 = boto3.client('s3')

# production step function
BASE_ARN = 'arn:aws:states:us-east-1:643366669028:%s:%s'
WORKFLOW_NAME = 'tibanna_pony'
STEP_FUNCTION_ARN = BASE_ARN % ('stateMachine', WORKFLOW_NAME)

# logger
LOG = logging.getLogger(__name__)


# custom exceptions to control retry logic in step functions
class StillRunningException(Exception):
    pass


class EC2StartingException(Exception):
    pass


class AWSEMJobErrorException(Exception):
    pass


def ensure_list(val):
    if isinstance(val, (list, tuple)):
        return val
    return [val]


class s3Utils(object):

    def __init__(self, outfile_bucket=None, sys_bucket=None, raw_file_bucket=None, env=None):
        '''
        if we pass in env set the outfile and sys bucket from the environment
        '''
        if sys_bucket is None:
            # we use standardized naming schema, so s3 buckets always have same prefix
            sys_bucket = "elasticbeanstalk-%s-system" % env
            outfile_bucket = "elasticbeanstalk-%s-wfoutput" % env
            raw_file_bucket = "elasticbeanstalk-%s-files" % env

        self.sys_bucket = sys_bucket
        self.outfile_bucket = outfile_bucket
        self.raw_file_bucket = raw_file_bucket

    def get_access_keys(self):
        name = 'illnevertell'
        keys = self.get_key(keyfile_name=name)
        return keys

    def get_key(self, keyfile_name='illnevertell'):
        # Share secret encrypted S3 File
        response = s3.get_object(Bucket=self.sys_bucket,
                                 Key=keyfile_name,
                                 SSECustomerKey=os.environ.get("SECRET"),
                                 SSECustomerAlgorithm='AES256')
        akey = response['Body'].read()
        try:
            return json.loads(akey)
        except (ValueError, TypeError):
            # maybe its not json after all
            return akey

    def get_s3_keys(self):
        return self.get_key('sbgs3key')

    def read_s3(self, filename):
        response = s3.get_object(Bucket=self.outfile_bucket,
                                 Key=filename)
        LOG.info(str(response))
        return response['Body'].read()

    def does_key_exist(self, key, bucket=None):
        if not bucket:
            bucket = self.outfile_bucket
        try:
            file_metadata = s3.head_object(Bucket=bucket,
                                           Key=key)
        except Exception as e:
            print("object %s not found on bucket %s" % (str(key), str(bucket)))
            print(str(e))
            return False
        return file_metadata

    def get_file_size(self, key, bucket=None, add_bytes=0, add_gb=0,
                      size_in_gb=False):
        '''
        default returns file size in bytes,
        unless size_in_gb = True
        '''
        meta = self.does_key_exist(key, bucket)
        if not meta:
            raise Exception("key not found")
        one_gb = 1073741824
        add = add_bytes + (add_gb * one_gb)
        size = meta['ContentLength'] + add
        if size_in_gb:
            size = size / one_gb
        return size

    def delete_key(self, key, bucket=None):
        if not bucket:
            bucket = self.outfile_bucket
        s3.delete_object(Bucket=bucket, Key=key)

    def size(self, bucket):
        sbuck = boto3.resource('s3').Bucket(bucket)
        # get only head of objects so we can count them
        return sum(1 for _ in sbuck.objects.all())

    def s3_put(self, obj, upload_key, acl=None):
        '''
        try to guess content type
        '''
        content_type = mimetypes.guess_type(upload_key)[0]
        if content_type is None:
            content_type = 'binary/octet-stream'
        if acl:
            # we use this to set some of the object as public
            s3.put_object(Bucket=self.outfile_bucket,
                          Key=upload_key,
                          Body=obj,
                          ContentType=content_type,
                          ACL=acl
                          )
        else:
            s3.put_object(Bucket=self.outfile_bucket,
                          Key=upload_key,
                          Body=obj,
                          ContentType=content_type
                          )

    def s3_read_dir(self, prefix):
        return s3.list_objects(Bucket=self.outfile_bucket,
                               Prefix=prefix)

    def s3_delete_dir(self, prefix):
        # one query get list of all the files we want to delete
        obj_list = s3.list_objects(Bucket=self.outfile_bucket,
                                   Prefix=prefix)
        files = obj_list.get('Contents', [])

        # morph file list into format that boto3 wants
        delete_keys = {'Objects': []}
        delete_keys['Objects'] = [{'Key': k} for k in
                                  [obj['Key'] for obj in files]]

        # second query deletes all the files, NOTE: Max 1000 files
        if delete_keys['Objects']:
            s3.delete_objects(Bucket=self.outfile_bucket,
                              Delete=delete_keys)

    def read_s3_zipfile(self, s3key, files_to_extract):
        s3_stream = self.read_s3(s3key)
        bytestream = BytesIO(s3_stream)
        zipstream = ZipFile(bytestream, 'r')
        ret_files = {}

        for name in files_to_extract:
            # search subdirectories for file with name
            # so I don't have to worry about figuring out the subdirs
            zipped_filename = find_file(name, zipstream)
            if zipped_filename:
                ret_files[name] = zipstream.open(zipped_filename).read()
        return ret_files

    def unzip_s3_to_s3(self, zipped_s3key, dest_dir, retfile_names=None, acl=None):
        if retfile_names is None:
            retfile_names = []

        if not dest_dir.endswith('/'):
            dest_dir += '/'

        s3_stream = self.read_s3(zipped_s3key)
        # read this badboy to memory, don't go to disk
        bytestream = BytesIO(s3_stream)
        zipstream = ZipFile(bytestream, 'r')

        # directory should be first name in the list
        file_list = zipstream.namelist()
        basedir_name = file_list.pop(0)
        assert basedir_name.endswith('/')

        ret_files = {}
        for file_name in file_list:
            # don't copy dirs just files
            if not file_name.endswith('/'):
                s3_file_name = file_name.replace(basedir_name, dest_dir)
                s3_key = "https://s3.amazonaws.com/%s/%s" % (self.outfile_bucket, s3_file_name)
                # just perf optimization so we don't have to copy
                # files twice that we want to further interogate
                the_file = zipstream.open(file_name, 'r').read()
                file_to_find = file_name.split('/')[-1]
                if file_to_find in retfile_names:
                    ret_files[file_to_find] = {'s3key': s3_key,
                                               'data': the_file}
                self.s3_put(the_file, s3_file_name, acl=acl)

        return ret_files


def find_file(name, zipstream):
    for zipped_filename in zipstream.namelist():
        if zipped_filename.endswith(name):
            return zipped_filename


def run_workflow(input_json, accession='', workflow='tibanna_pony',
                 env='fourfront-webdev'):
    '''
    accession is unique name that we be part of run id
    '''
    client = boto3.client('stepfunctions', region_name='us-east-1')
    STEP_FUNCTION_ARN = BASE_ARN % ('stateMachine', str(workflow))
    base_url = 'https://console.aws.amazon.com/states/home?region=us-east-1#/executions/details/'

    # build from appropriate input json
    # assume run_type and and run_id
    input_json = _tibanna_settings(input_json, force_inplace=True, env=env)
    run_name = input_json[_tibanna]['run_name']

    # check to see if run already exists
    # and if so change our name a bit
    arn = "%s%s%s" % (BASE_ARN % ('execution', str(workflow)),
                      ":",
                      run_name)
    try:
        response = client.describe_execution(
                executionArn=arn
        )
        if response:
            run_name += str(uuid4())
            input_json[_tibanna]['run_name'] = run_name
    except Exception as e:
        pass

    # calculate what the url will be
    url = "%s%s%s%s" % (base_url,
                        BASE_ARN % ('execution', str(workflow)),
                        ":",
                        run_name)

    input_json[_tibanna]['url'] = url

    aws_input = json.dumps(input_json)
    print("about to start run %s" % run_name)
    # trigger the step function to run
    try:
        response = client.start_execution(
            stateMachineArn=STEP_FUNCTION_ARN,
            name=run_name,
            input=aws_input,
        )
    except Exception as e:
        if e.response.get('Error'):
            if e.response['Error'].get('Code') == 'ExecutionAlreadyExists':
                print("execution already exists...mangling name and retrying...")
                run_name += str(uuid4())
                input_json[_tibanna]['run_name'] = run_name

                # calculate what the url will be
                url = "%s%s%s%s" % (base_url, (BASE_ARN % 'execution'), ":", run_name)
                input_json[_tibanna]['url'] = url
                aws_input = json.dumps(input_json)

                response = client.start_execution(
                    stateMachineArn=STEP_FUNCTION_ARN,
                    name=run_name,
                    input=aws_input,
                )
            else:
                raise(e)

    print("response from aws was: \n %s" % response)
    print("url to view status:")
    print(input_json[_tibanna]['url'])
    input_json[_tibanna]['response'] = response
    return input_json


def create_stepfunction(dev_suffix='dev',
                        sfn_type='pony',  # vs 'unicorn'
                        region_name='us-east-1',
                        aws_acc='643366669028'):
    lambda_suffix = '_' + dev_suffix
    sfn_name = 'tibanna_' + sfn_type + lambda_suffix
    lambda_arn_prefix = "arn:aws:lambda:" + region_name + ":" + aws_acc + ":function:"
    sfn_role_arn = "arn:aws:iam::" + aws_acc + ":role/service-role/StatesExecutionRole-" + region_name
    sfn_check_task_retry_conditions = [
        {
            "ErrorEquals": ["EC2StartingException"],
            "IntervalSeconds": 300,
            "MaxAttempts": 4,
            "BackoffRate": 1.0
        },
        {
            "ErrorEquals": ["StillRunningException"],
            "IntervalSeconds": 600,
            "MaxAttempts": 10000,
            "BackoffRate": 1.0
        }
    ]
    sfn_start_lambda = {'pony': 'StartRunAwsem', 'unicorn': 'RunTaskAwsem'}
    sfn_state_defs = dict()
    sfn_state_defs['pony'] = {
        "StartRunAwsem": {
            "Type": "Task",
            "Resource": lambda_arn_prefix + "start_run_awsem" + lambda_suffix,
            "Next": "RunTaskAwsem"
        },
        "RunTaskAwsem": {
            "Type": "Task",
            "Resource": lambda_arn_prefix + "run_task_awsem" + lambda_suffix,
            "Next": "CheckTaskAwsem"
        },
        "CheckTaskAwsem": {
            "Type": "Task",
            "Resource": lambda_arn_prefix + "check_task_awsem" + lambda_suffix,
            "Retry": sfn_check_task_retry_conditions,
            "Next": "UpdateFFMetaAwsem"
        },
        "UpdateFFMetaAwsem": {
            "Type": "Task",
            "Resource": lambda_arn_prefix + "update_ffmeta_awsem" + lambda_suffix,
            "End": True
        }
    }
    sfn_state_defs['unicorn'] = {
        "RunTaskAwsem": {
            "Type": "Task",
            "Resource": lambda_arn_prefix + "run_task_awsem" + lambda_suffix,
            "Next": "CheckTaskAwsem"
        },
        "CheckTaskAwsem": {
            "Type": "Task",
            "Resource": lambda_arn_prefix + "check_task_awsem" + lambda_suffix,
            "Retry": sfn_check_task_retry_conditions,
            "End": True
        }
    }
    definition = {
      "Comment": "Start a workflow run on awsem, (later) track it and update our metadata to reflect whats going on",
      "StartAt": sfn_start_lambda[sfn_type],
      "States": sfn_state_defs[sfn_type]
    }
    client = boto3.client('stepfunctions', region_name=region_name)
    try:
        response = client.create_state_machine(
            name=sfn_name,
            definition=json.dumps(definition, indent=4, sort_keys=True),
            roleArn=sfn_role_arn
        )
    except Exception as e:
        # sfn_arn=None
        raise(e)
    # sfn_arn = response['stateMachineArn']
    return(response)


# just store this in one place
_tibanna = '_tibanna'


class Tibanna(object):

    def __init__(self, env, s3_keys=None, ff_keys=None, sbg_keys=None, settings=None):
        self.env = env
        self.s3 = s3Utils(env=env)

        if not s3_keys:
            s3_keys = self.s3.get_s3_keys()
        self.s3_keys = s3_keys

        if not ff_keys:
            ff_keys = self.s3.get_access_keys()
        self.ff_keys = ff_keys

        # we don't need this unless we switch back to sbg, let's remove for now
        # if not sbg_keys:
        #    sbg_keys = self.s3.get_sbg_keys()

        if not settings:
            settings = {}
        self.settings = settings

    def get_reporter(self):
        '''
        a reporter is a generic name for somethign that reports on the results of each step
        of the workflow.  For our immediate purposes this will return ffmetadata object
        (which is a connection to our metadata repository, eventually it should, through
        polymorphism support any type of reporter a user might develop.
        '''
        return None

    def get_runner(self):
        '''
        a runner is an object that implements a set api to run the workflow one step at a time.
        Currently this is sbg for us.
        '''
        return None

    def as_dict(self):
        return {'env': self.env,
                'settings': self.settings}


def _tibanna_settings(settings_patch=None, force_inplace=False, env=''):
    tibanna = {"run_id": str(uuid4()),
               "env": env,
               "url": '',
               'run_type': 'generic',
               'run_name': '',
               }
    in_place = None
    if force_inplace:
        if not settings_patch.get(_tibanna):
            settings_patch[_tibanna] = {}
    if settings_patch:
        in_place = settings_patch.get(_tibanna, None)
        if in_place is not None:
            tibanna.update(in_place)
        else:
            tibanna.update(settings_patch)

    # generate run name
    if not tibanna.get('run_name'):
        # aws doesn't like / in names
        tibanna['run_name'] = "%s_%s" % (tibanna['run_type'].replace('/', '-'), tibanna['run_id'])

    if in_place is not None:
        settings_patch[_tibanna] = tibanna
        return settings_patch
    else:
        return {_tibanna: tibanna}


def get_files_to_match(tibanna, query, frame='object'):
    return get_metadata(query, key=tibanna.ff_keys)


def current_env():
    return os.environ.get('ENV_NAME', 'test')


def is_prod():
    return current_env().lower() == 'prod'


def powerup(lambda_name, metadata_only_func, run_if_error=False):
    '''
    friendly wrapper for your lambda functions, based on input_json / event comming in...
    1. Logs basic input for all functions
    2. if 'skip' key == 'lambda_name', skip the function
    3. catch exceptions raised by labmda, and if not in  list of ignored exceptions, added
       the exception to output json
    4. if input json has 'error' key, skip function unless `run_if_error` is provided
    5. 'metadata' only parameter, if set to true, just create metadata instead of run workflow

    '''
    def decorator(function):
        import logging
        logging.basicConfig()
        logger = logging.getLogger('logger')
        ignored_exceptions = [EC2StartingException, StillRunningException, ]

        def wrapper(event, context):
            logger.info(context)
            logger.info(event)
            if lambda_name in event.get('skip', []):
                logger.info('skiping %s since skip was set in input_json' % lambda_name)
                return event
            elif event.get('metadata_only', False):
                return metadata_only_func(event)
            else:
                try:
                    return function(event, context)
                except Exception as e:
                    if type(e) in ignored_exceptions:
                        raise e
                        # update ff_meta to error status
                    elif lambda_name == 'update_ffmeta_awsem':
                        # for last step just pit out error
                        raise e
                    else:
                        event['error'] = str(e)
                        logger.info(e)
                        return event
        return wrapper
    return decorator
