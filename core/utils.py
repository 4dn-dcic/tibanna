from core.iam_utils import get_stepfunction_role_name
import random
import string
import logging
import traceback
import os
import boto3
import json
from uuid import uuid4, UUID
import time
import copy

###########################################
# These utils exclusively live in Tibanna #
###########################################


LOG = logging.getLogger(__name__)


def printlog(message):
    print(message)
    LOG.info(message)


AWS_ACCOUNT_NUMBER = os.environ.get('AWS_ACCOUNT_NUMBER', '')
AWS_REGION = os.environ.get('TIBANNA_AWS_REGION', '')
BASE_ARN = 'arn:aws:states:' + AWS_REGION + ':' + AWS_ACCOUNT_NUMBER + ':%s:%s'
TIBANNA_DEFAULT_STEP_FUNCTION_NAME = os.environ.get('TIBANNA_DEFAULT_STEP_FUNCTION_NAME', 'tibanna_pony')
DYNAMODB_TABLE = 'tibanna-master'
BASE_EXEC_ARN = 'arn:aws:states:' + AWS_REGION + ':' + AWS_ACCOUNT_NUMBER + ':execution:%s:%s'

# just store this in one place
_tibanna = '_tibanna'


def STEP_FUNCTION_ARN(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    return BASE_ARN % ('stateMachine', sfn)


def EXECUTION_ARN(exec_name, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    return BASE_EXEC_ARN % (sfn, exec_name)


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


class DependencyStillRunningException(Exception):
    pass


class DependencyFailedException(Exception):
    pass


class EC2LaunchException(Exception):
    pass


class EC2UnintendedTerminationException(Exception):
    pass


class EC2IdleException(Exception):
    pass


class EC2InstanceLimitException(Exception):
    pass


class EC2InstanceLimitWaitException(Exception):
    pass


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
                              TibannaStartException, FdnConnectionException,
                              DependencyStillRunningException, EC2InstanceLimitWaitException]

        def wrapper(event, context):
            if context:
                logger.info(context)
            logger.info(event)
            if lambda_name in event.get('skip', []):
                logger.info('skipping %s since skip was set in input_json' % lambda_name)
                return event
            elif event.get('push_error_to_end', False) and event.get('error', False) \
                    and lambda_name != 'update_ffmeta_awsem':
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
                        if 'error' in event:
                            error_msg = "error from earlier step: %s" % event["error"]
                        else:
                            error_msg = "error from update_ffmeta: %s" % str(e)
                        raise Exception(error_msg)
                    elif not event.get('push_error_to_end', False):
                        raise e
                    else:
                        if e.__class__ == AWSEMJobErrorException:
                            error_msg = 'Error on step: %s: %s' % (lambda_name, str(e))
                        elif e.__class__ == EC2UnintendedTerminationException:
                            error_msg = 'EC2 unintended termination error on step: %s: %s' % (lambda_name, str(e))
                        elif e.__class__ == EC2IdleException:
                            error_msg = 'EC2 Idle error on step: %s: %s' % (lambda_name, str(e))
                        else:
                            error_msg = 'Error on step: %s. Full traceback: %s' % (lambda_name, traceback.format_exc())
                        event['error'] = error_msg
                        logger.info(error_msg)
                        return event
        return wrapper
    return decorator


def randomize_run_name(run_name, sfn):
    arn = get_exec_arn(sfn, run_name)
    client = boto3.client('stepfunctions', region_name='us-east-1')
    try:
        response = client.describe_execution(
                executionArn=arn
        )
        if response:
            if len(run_name) > 36:
                try:
                    UUID(run_name[-36:])
                    run_name = run_name[:-37]  # remove previous uuid
                except:
                    pass
            run_name += '-' + str(uuid4())

    except Exception:
        pass
    return run_name


# random string generator
def randomword(length):
    choices = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return ''.join(random.choice(choices) for i in range(length))


def create_jobid():
    return randomword(12)    # date+random_string


def get_exec_arn(sfn, run_name):
    arn = "%s%s%s" % (BASE_ARN % ('execution', str(sfn)),
                      ":",
                      run_name)
    return arn


def run_workflow(input_json, accession='', sfn='tibanna_pony',
                 env='fourfront-webdev', jobid=None, sleep=3):
    '''
    accession is unique name that we be part of run id
    '''
    client = boto3.client('stepfunctions', region_name='us-east-1')
    base_url = 'https://console.aws.amazon.com/states/home?region=us-east-1#/executions/details/'

    input_json_copy = copy.deepcopy(input_json)

    # build from appropriate input json
    # assume run_type and and run_id
    if 'run_name' in input_json_copy['config']:
        if _tibanna not in input_json_copy:
            input_json_copy[_tibanna] = dict()
        input_json_copy[_tibanna]['run_name'] = input_json_copy['config']['run_name']
    input_json_copy = _tibanna_settings(input_json_copy, force_inplace=True, env=env)
    run_name = randomize_run_name(input_json_copy[_tibanna]['run_name'], sfn)
    input_json_copy[_tibanna]['run_name'] = run_name
    input_json_copy['config']['run_name'] = run_name

    # updated arn
    arn = get_exec_arn(sfn, run_name)
    input_json_copy[_tibanna]['exec_arn'] = arn

    # calculate what the url will be
    url = "%s%s" % (base_url, arn)
    input_json_copy[_tibanna]['url'] = url

    # add jobid
    if not jobid:
        jobid = create_jobid()
    input_json_copy['jobid'] = jobid

    aws_input = json.dumps(input_json_copy)
    print("about to start run %s" % run_name)
    # trigger the step function to run
    try:
        response = client.start_execution(
            stateMachineArn=STEP_FUNCTION_ARN(sfn),
            name=run_name,
            input=aws_input,
        )
        time.sleep(sleep)
    except Exception as e:
        raise(e)
    # adding execution info to dynamoDB for fast search by awsem job id
    add_to_dydb(jobid, run_name, sfn, input_json_copy['config']['log_bucket'])
    # print some info
    print("response from aws was: \n %s" % response)
    print("url to view status:")
    print(input_json_copy[_tibanna]['url'])
    input_json_copy[_tibanna]['response'] = response
    return input_json_copy


def add_to_dydb(awsem_job_id, execution_name, sfn, logbucket):
    dydb = boto3.client('dynamodb')
    try:
        # first check the table exists
        dydb.describe_table(TableName=DYNAMODB_TABLE)
    except Exception as e:
        printlog("Not adding to dynamo table: %s" % e)
        return
    try:
        response = dydb.put_item(
            TableName=DYNAMODB_TABLE,
            Item={
                'Job Id': {
                    'S': awsem_job_id
                },
                'Execution Name': {
                    'S': execution_name
                },
                'Step Function': {
                    'S': sfn
                },
                'Log Bucket': {
                    'S': logbucket
                },
            }
        )
        printlog(response)
    except Exception as e:
        raise(e)


def create_stepfunction(dev_suffix=None,
                        sfn_type='pony',  # vs 'unicorn'
                        region_name=AWS_REGION,
                        aws_acc=AWS_ACCOUNT_NUMBER,
                        usergroup=None):
    if not aws_acc or not region_name:
        print("Please set and export environment variable AWS_ACCOUNT_NUMBER and AWS_REGION!")
        exit(1)
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
    if sfn_type == 'pony' or not usergroup:  # 4dn
        sfn_role_arn = "arn:aws:iam::" + aws_acc + ":role/service-role/StatesExecutionRole-" + region_name
    else:
        sfn_role_arn = "arn:aws:iam::" + aws_acc + ":role/" + \
            get_stepfunction_role_name('tibanna_' + usergroup)
    sfn_check_task_retry_conditions = [
        {
            "ErrorEquals": ["EC2StartingException"],
            "IntervalSeconds": 300,
            "MaxAttempts": 25,
            "BackoffRate": 1.0
        },
        {
            "ErrorEquals": ["StillRunningException"],
            "IntervalSeconds": 300,
            "MaxAttempts": 100000,
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
    sfn_run_task_retry_conditions = [
        {
            "ErrorEquals": ["DependencyStillRunningException"],
            "IntervalSeconds": 600,
            "MaxAttempts": 10000,
            "BackoffRate": 1.0
        },
        {
            "ErrorEquals": ["EC2InstanceLimitWaitException"],
            "IntervalSeconds": 600,
            "MaxAttempts": 1008,  # 1 wk
            "BackoffRate": 1.0
        }
    ]
    sfn_update_ff_meta_retry_conditions = [
        {
            "ErrorEquals": ["TibannaStartException"],
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
            "Retry": sfn_run_task_retry_conditions,
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
            "Retry": sfn_update_ff_meta_retry_conditions,
            "End": True
        }
    }
    sfn_state_defs['unicorn'] = {
        "RunTaskAwsem": {
            "Type": "Task",
            "Resource": lambda_arn_prefix + "run_task_awsem" + lambda_suffix,
            "Retry": sfn_run_task_retry_conditions,
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
    # if this encouters an existing step function with the same name, delete
    sfn = boto3.client('stepfunctions', region_name=region_name)
    retries = 12  # wait 10 seconds between retries for total of 120s
    response = None
    for i in range(retries):
        try:
            response = sfn.create_state_machine(
                name=sfn_name,
                definition=json.dumps(definition, indent=4, sort_keys=True),
                roleArn=sfn_role_arn
            )
        except sfn.exceptions.StateMachineAlreadyExists as e:
            # get ARN from the error and format as necessary
            exc_str = str(e)
            if 'State Machine Already Exists:' not in exc_str:
                print('Cannot delete state machine. Exiting...' % exc_str)
                raise(e)
            sfn_arn = exc_str.split('State Machine Already Exists:')[-1].strip().strip("''")
            print('Step function with name %s already exists!\nUpdating the state machine...' % sfn_name)
            try:
                response = sfn.update_state_machine(
                    stateMachineArn=sfn_arn,
                    definition=json.dumps(definition, indent=4, sort_keys=True),
                    roleArn=sfn_role_arn
                )
            except Exception as e:
                print('Error updating state machine %s' % str(e))
                raise(e)
        except Exception as e:
            raise(e)
        break
    return sfn_name


def check_dependency(exec_arn=None):
    if exec_arn:
        client = boto3.client('stepfunctions', region_name=AWS_REGION)
        for arn in exec_arn:
            res = client.describe_execution(executionArn=arn)
            if res['status'] == 'RUNNING':
                raise DependencyStillRunningException("Dependency is still running: %s" % arn)
            elif res['status'] == 'FAILED':
                raise DependencyFailedException("A Job that this job is dependent on failed: %s" % arn)


def check_status(exec_arn):
    '''checking status of an execution'''
    sts = boto3.client('stepfunctions', region_name=AWS_REGION)
    return sts.describe_execution(executionArn=exec_arn)['status']


def check_output(exec_arn):
    '''checking status of an execution first and if it's success, get output'''
    sts = boto3.client('stepfunctions', region_name=AWS_REGION)
    if check_status(exec_arn) == 'SUCCEEDED':
        desc = sts.describe_execution(executionArn=exec_arn)
        if 'output' in desc:
            return json.loads(desc['output'])
        else:
            return None


def kill(exec_arn=None, job_id=None, sfn=None):
    sf = boto3.client('stepfunctions')
    if exec_arn:
        desc = sf.describe_execution(executionArn=exec_arn)
        if desc['status'] == 'RUNNING':
            jobid = str(json.loads(desc['input'])['jobid'])
            ec2 = boto3.resource('ec2')
            terminated = None
            for i in ec2.instances.all():
                if i.tags:
                    for tag in i.tags:
                        if tag['Key'] == 'Type' and tag['Value'] != 'awsem':
                            continue
                        if tag['Key'] == 'Name' and tag['Value'] == 'awsem-' + jobid:
                            printlog("terminating EC2 instance")
                            response = i.terminate()
                            printlog(response)
                            terminated = True
                            break
                    if terminated:
                        break
            printlog("terminating step function execution")
            resp_sf = sf.stop_execution(executionArn=exec_arn, error="Aborted")
            printlog(resp_sf)
    elif job_id:
        ec2 = boto3.client('ec2')
        res = ec2.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': ['awsem-' + job_id]}])
        if not res['Reservations']:
            raise("instance not available - if you just submitted the job, try again later")
        instance_id = res['Reservations'][0]['Instances'][0]['InstanceId']
        printlog("terminating EC2 instance")
        resp_term = ec2.terminate_instances(InstanceIds=[instance_id])
        printlog(resp_term)
        if not sfn:
            printlog("Can't stop step function because step function name is not given.")
            return None
        stateMachineArn = STEP_FUNCTION_ARN(sfn)
        res = sf.list_executions(stateMachineArn=stateMachineArn, statusFilter='RUNNING')
        while True:
            if 'executions' not in res or not res['executions']:
                break
            for exc in res['executions']:
                desc = sf.describe_execution(executionArn=exc['executionArn'])
                if job_id == str(json.loads(desc['input'])['jobid']):
                    printlog("terminating step function execution")
                    resp_sf = sf.stop_execution(executionArn=exc['executionArn'], error="Aborted")
                    printlog(resp_sf)
                    break
            if 'nextToken' in res:
                res = sf.list_executions(nextToken=res['nextToken'],
                                         stateMachineArn=stateMachineArn, statusFilter='RUNNING')
            else:
                break


def kill_all(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    """killing all the running jobs"""
    client = boto3.client('stepfunctions')
    stateMachineArn = STEP_FUNCTION_ARN(sfn)
    res = client.list_executions(stateMachineArn=stateMachineArn, statusFilter='RUNNING')
    while True:
        if 'executions' not in res or not res['executions']:
            break
        for exc in res['executions']:
            kill(exc['executionArn'])
        if 'nextToken' in res:
            res = client.list_executions(nextToken=res['nextToken'],
                                         stateMachineArn=stateMachineArn, statusFilter='RUNNING')
        else:
            break


# fix non json-serializable datetime startDate
def serialize_startdate(response):
    tibanna_resp = response.get('_tibanna', {}).get('response')
    if tibanna_resp and tibanna_resp.get('startDate'):
        tibanna_resp['startDate'] = str(tibanna_resp['startDate'])


def send_notification_email(job_name, jobid, status, exec_url=None, sender='4dndcic@gmail.com'):
    subject = '[Tibanna] job %s : %s' % (status, job_name)
    msg = 'Job %s (%s) finished with status %s\n' % (jobid, job_name, status) \
          + 'For more detail, go to %s' % exec_url
    client = boto3.client('ses')
    client.send_email(Source=sender,
                      Destination={'ToAddresses': [sender]},
                      Message={'Subject': {'Data': subject},
                               'Body': {'Text': {'Data': msg}}})


def log(exec_arn=None, job_id=None, exec_name=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, postrunjson=False):
    if postrunjson:
        suffix = '.postrun.json'
    else:
        suffix = '.log'
    sf = boto3.client('stepfunctions')
    if not exec_arn and exec_name:
        exec_arn = EXECUTION_ARN(exec_name, sfn)
    if exec_arn:
        desc = sf.describe_execution(executionArn=exec_arn)
        jobid = str(json.loads(desc['input'])['jobid'])
        logbucket = str(json.loads(desc['input'])['config']['log_bucket'])
        res_s3 = boto3.client('s3').get_object(Bucket=logbucket, Key=jobid + suffix)
        if res_s3:
            return(res_s3['Body'].read())
    elif job_id:
        stateMachineArn = STEP_FUNCTION_ARN(sfn)
        res = sf.list_executions(stateMachineArn=stateMachineArn)
        while True:
            if 'executions' not in res or not res['executions']:
                break
            for exc in res['executions']:
                desc = sf.describe_execution(executionArn=exc['executionArn'])
                if job_id == str(json.loads(desc['input'])['jobid']):
                    logbucket = str(json.loads(desc['input'])['config']['log_bucket'])
                    res_s3 = boto3.client('s3').get_object(Bucket=logbucket, Key=job_id + suffix)
                    if res_s3:
                        return(res_s3['Body'].read())
                    break
            if 'nextToken' in res:
                res = sf.list_executions(nextToken=res['nextToken'],
                                         stateMachineArn=stateMachineArn)
            else:
                break
    return None


def read_s3(bucket, object_name):
    response = boto3.client('s3').get_object(Bucket=bucket, Key=object_name)
    printlog(str(response))
    return response['Body'].read()

