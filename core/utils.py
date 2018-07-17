from __future__ import print_function
import json
import boto3
import os
import datetime
from uuid import uuid4
from dcicutils.ff_utils import (
    get_metadata,
    post_metadata,
    patch_metadata,
    generate_rand_accession
)
from dcicutils.s3_utils import s3Utils
import logging
import traceback

###########################################
# These utils exclusively live in Tibanna #
###########################################


###########################
# Config
###########################

# production step function
AWS_ACCOUNT_NUMBER = os.environ.get('AWS_ACCOUNT_NUMBER')
AWS_REGION = os.environ.get('TIBANNA_AWS_REGION')
BASE_ARN = 'arn:aws:states:' + AWS_REGION + ':' + AWS_ACCOUNT_NUMBER + ':%s:%s'
WORKFLOW_NAME = 'tibanna_pony'
STEP_FUNCTION_ARN = BASE_ARN % ('stateMachine', WORKFLOW_NAME)
# just store this in one place
_tibanna = '_tibanna'

# logger
LOG = logging.getLogger(__name__)


# custom exceptions to control retry logic in step functions
class StillRunningException(Exception):
    pass


class EC2StartingException(Exception):
    pass


class AWSEMJobErrorException(Exception):
    pass


class TibannaStartException(Exception):
    pass


class FdnConnectionException(Exception):
    pass


def create_ffmeta_awsem(workflow, app_name, input_files=None,
                        parameters=None, title=None, uuid=None,
                        output_files=None, award='1U01CA200059-01', lab='4dn-dcic-lab',
                        run_status='started', run_platform='AWSEM', run_url='', tag=None,
                        aliases=None, awsem_postrun_json=None, submitted_by=None, extra_meta=None,
                        **kwargs):

    input_files = [] if input_files is None else input_files
    parameters = [] if parameters is None else parameters
    if award is None:
        award = '1U01CA200059-01'
    if lab is None:
        lab = '4dn-dcic-lab'

    if title is None:
        if tag is None:
            title = app_name + " run " + str(datetime.datetime.now())
        else:
            title = app_name + ' ' + tag + " run " + str(datetime.datetime.now())

    return WorkflowRunMetadata(workflow=workflow, app_name=app_name, input_files=input_files,
                               parameters=parameters, uuid=uuid, award=award,
                               lab=lab, run_platform=run_platform, run_url=run_url,
                               title=title, output_files=output_files, run_status=run_status,
                               aliases=aliases, awsem_postrun_json=awsem_postrun_json,
                               submitted_by=submitted_by, extra_meta=extra_meta)


class WorkflowRunMetadata(object):
    '''
    fourfront metadata
    '''

    def __init__(self, workflow, app_name, input_files=[],
                 parameters=[], uuid=None,
                 award='1U01CA200059-01', lab='4dn-dcic-lab',
                 run_platform='AWSEM', title=None, output_files=None,
                 run_status='started', awsem_job_id=None,
                 run_url='', aliases=None, awsem_postrun_json=None,
                 submitted_by=None, extra_meta=None, **kwargs):
        """Class for WorkflowRun that matches the 4DN Metadata schema
        Workflow (uuid of the workflow to run) has to be given.
        Workflow_run uuid is auto-generated when the object is created.
        """
        if run_platform == 'AWSEM':
            self.awsem_app_name = app_name
            # self.app_name = app_name
            if awsem_job_id is None:
                self.awsem_job_id = ''
            else:
                self.awsem_job_id = awsem_job_id
        else:
            raise Exception("invalid run_platform {} - it must be AWSEM".format(run_platform))

        self.run_status = run_status
        self.uuid = uuid if uuid else str(uuid4())
        self.workflow = workflow
        self.run_platform = run_platform
        if run_url:
            self.run_url = run_url

        self.title = title
        if aliases:
            if isinstance(aliases, basestring):  # noqa
                aliases = [aliases, ]
            self.aliases = aliases
        self.input_files = input_files
        if output_files:
            self.output_files = output_files
        self.parameters = parameters
        self.award = award
        self.lab = lab
        if awsem_postrun_json:
            self.awsem_postrun_json = awsem_postrun_json
        if submitted_by:
            self.submitted_by = submitted_by

        if extra_meta:
            for k, v in extra_meta.iteritems():
                self.__dict__[k] = v

    def append_outputfile(self, outjson):
        self.output_files.append(outjson)

    def as_dict(self):
        return self.__dict__

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def post(self, key, type_name=None):
        if not type_name:
            if self.run_platform == 'AWSEM':
                type_name = 'workflow_run_awsem'
            else:
                raise Exception("cannot determine workflow schema type from the run platform: should be AWSEM.")
        return post_metadata(self.as_dict(), type_name, key=key)

    def patch(self, key, type_name=None):
        return patch_metadata(self.as_dict(), key=key)


class ProcessedFileMetadata(object):
    def __init__(self, uuid=None, accession=None, file_format='', lab='4dn-dcic-lab',
                 extra_files=None, source_experiments=None,
                 award='1U01CA200059-01', status='to be uploaded by workflow',
                 md5sum=None, file_size=None, other_fields=None, **kwargs):
        self.uuid = uuid if uuid else str(uuid4())
        self.accession = accession if accession else generate_rand_accession()
        self.status = status
        self.lab = lab
        self.award = award
        self.file_format = file_format
        if extra_files:
            self.extra_files = extra_files
        if source_experiments:
            self.source_experiments = source_experiments
        if md5sum:
            self.md5sum = md5sum
        if file_size:
            self.file_size = file_size
        if other_fields:
            for field in other_fields:
                setattr(self, field, other_fields[field])

    def as_dict(self):
        return self.__dict__

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def post(self, key):
        return post_metadata(self.as_dict(), "file_processed", key=key, add_on='force_md5')

    def patch(self, key):
        return patch_metadata(self.as_dict(), key=key, add_on='force_md5')

    @classmethod
    def get(cls, uuid, key, ff_env=None, check_queue=False, return_data=False):
        data = get_metadata(uuid,
                            key=key,
                            ff_env=ff_env,
                            add_on='frame=object',
                            check_queue=check_queue)
        if type(data) is not dict:
            raise Exception("unable to find object with unique key of %s" % uuid)
        if 'FileProcessed' not in data.get('@type', {}):
            raise Exception("you can only load ProcessedFiles into this object")

        pf = ProcessedFileMetadata(**data)
        if return_data:
            return pf, data
        else:
            return pf


def aslist(x):
    if isinstance(x, list):
        return x
    else:
        return [x]


def ensure_list(val):
    if isinstance(val, (list, tuple)):
        return val
    return [val]


def get_extra_file_key(infile_format, infile_key, extra_file_format, fe_map):
    infile_extension = fe_map.get(infile_format)
    extra_file_extension = fe_map.get(extra_file_format)
    return infile_key.replace(infile_extension, extra_file_extension)


def get_format_extension_map(ff_keys):
    try:
        fp_schema = get_metadata("profiles/file_processed.json", key=ff_keys)
        fe_map = fp_schema.get('file_format_file_extension')
    except Exception as e:
        raise Exception("Can't get format-extension map from file_processed schema. %s\n" % e)
    return fe_map


def get_source_experiment(input_file_uuid, ff_keys, ff_env):
    """
    Connects to fourfront and get source experiment info as a unique list
    Takes a single input file uuid.
    """
    pf_source_experiments_set = set()
    inf_uuids = aslist(input_file_uuid)
    for inf_uuid in inf_uuids:
        infile_meta = get_metadata(inf_uuid,
                                   key=ff_keys,
                                   ff_env=ff_env,
                                   add_on='frame=object')
        if infile_meta.get('experiments'):
            for exp in infile_meta.get('experiments'):
                exp_obj = get_metadata(exp,
                                       key=ff_keys,
                                       ff_env=ff_env,
                                       add_on='frame=raw')
                pf_source_experiments_set.add(exp_obj['uuid'])
        if infile_meta.get('source_experiments'):
            # this field is an array of strings, not linkTo's
            pf_source_experiments_set.update(infile_meta.get('source_experiments'))
    return list(pf_source_experiments_set)


def merge_source_experiments(input_file_uuids, ff_keys, ff_env=None):
    """
    Connects to fourfront and get source experiment info as a unique list
    Takes a list of input file uuids.
    """
    pf_source_experiments = set()
    for input_file_uuid in input_file_uuids:
        pf_source_experiments.update(get_source_experiment(input_file_uuid, ff_keys, ff_env))
    return list(pf_source_experiments)


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


def create_stepfunction(dev_suffix=None,
                        sfn_type='pony',  # vs 'unicorn'
                        region_name=AWS_REGION,
                        aws_acc=AWS_ACCOUNT_NUMBER,
                        usergroup=None):
    if usergroup:
        if dev_suffix:
            lambda_suffix = '_' + usergroup + '_' + dev_suffix
        else:
            lambda_suffix = '_' + usergroup
    else:
        if dev_suffix:
            lambda_suffix = '_' + dev_suffix
        else:
            lambda_suffix = ''
    sfn_name = 'tibanna_' + sfn_type + lambda_suffix
    lambda_arn_prefix = "arn:aws:lambda:" + region_name + ":" + aws_acc + ":function:"
    if sfn_type == 'pony':  # 4dn
        sfn_role_arn = "arn:aws:iam::" + aws_acc + ":role/service-role/StatesExecutionRole-" + region_name
    else:
        sfn_role_arn = "arn:aws:iam::" + aws_acc + ":role/" + \
            get_stepfunction_role_name('tibanna_' + usergroup)
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
    sfn_start_run_retry_conditions = [
        {
            "ErrorEquals": ["TibannaStartException"],
            "IntervalSeconds": 30,
            "MaxAttempts": 5,
            "BackoffRate": 1.0
        },
        {
            "ErrorEquals": ["FdnConnectionException"],
            "IntervalSeconds": 30,
            "MaxAttempts": 5,
            "BackoffRate": 1.0
        }
    ]
    sfn_start_lambda = {'pony': 'StartRunAwsem', 'unicorn': 'RunTaskAwsem'}
    sfn_state_defs = dict()
    sfn_state_defs['pony'] = {
        "StartRunAwsem": {
            "Type": "Task",
            "Resource": lambda_arn_prefix + "start_run_awsem" + lambda_suffix,
            "Retry": sfn_start_run_retry_conditions,
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


class Tibanna(object):

    def __init__(self, env, ff_keys=None, sbg_keys=None, settings=None):
        self.env = env
        self.s3 = s3Utils(env=env)

        if not ff_keys:
            ff_keys = self.s3.get_access_keys()
        self.ff_keys = ff_keys

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


def current_env():
    return os.environ.get('ENV_NAME', 'test')


def is_prod():
    return current_env().lower() == 'prod'


def powerup(lambda_name, metadata_only_func):
    '''
    friendly wrapper for your lambda functions, based on input_json / event comming in...
    1. Logs basic input for all functions
    2. if 'skip' key == 'lambda_name', skip the function
    3. catch exceptions raised by labmda, and if not in  list of ignored exceptions, added
       the exception to output json
    4. 'metadata' only parameter, if set to true, just create metadata instead of run workflow

    '''
    def decorator(function):
        import logging
        logging.basicConfig()
        logger = logging.getLogger('logger')
        ignored_exceptions = [EC2StartingException, StillRunningException,
                              TibannaStartException, FdnConnectionException]

        def wrapper(event, context):
            logger.info(context)
            logger.info(event)
            if lambda_name in event.get('skip', []):
                logger.info('skipping %s since skip was set in input_json' % lambda_name)
                return event
            elif event.get('error', False) and lambda_name != 'update_ffmeta_awsem':
                logger.info('skipping %s since a value for "error" is in input json '
                            'and lambda is not update_ffmeta_awsem' % lambda_name)
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
                        error_msg = 'Error on step: %s. Full traceback: %s' % (lambda_name, traceback.format_exc())
                        event['error'] = error_msg
                        logger.info(error_msg)
                        return event
        return wrapper
    return decorator
