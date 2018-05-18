from __future__ import print_function
import json
import boto3
import os
from uuid import uuid4
from dcicutils.ff_utils import get_metadata
from dcicutils.tibanna_utils import aslist
from dcicutils.submit_utils import FdnConnectionException
from dcicutils.s3_utils import s3Utils
import logging

###########################################
# These utils exclusively live in Tibanna #
###########################################

###########################
# Config
###########################

# production step function
BASE_ARN = 'arn:aws:states:us-east-1:643366669028:%s:%s'
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
                                   frame='object',
                                   ensure=True)
        if infile_meta.get('experiments'):
            for exp in infile_meta.get('experiments'):
                exp_obj = get_metadata(exp,
                                       key=ff_keys,
                                       ff_env=ff_env,
                                       frame='raw',
                                       ensure=True)
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


def get_files_to_match(tibanna, query, frame='object'):
    return get_metadata(query,
                        key=tibanna.ff_keys,
                        ff_env=tibanna.env,
                        frame=frame,
                        ensure=True)


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
        ignored_exceptions = [EC2StartingException, StillRunningException,
                              TibannaStartException, FdnConnectionException]

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
