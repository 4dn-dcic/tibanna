import boto3
import json
from core.utils import run_workflow as _run_workflow
from core.utils import TIBANNA_DEFAULT_STEP_FUNCTION_NAME, STEP_FUNCTION_ARN
from datetime import datetime
import time
import os


###########################################
# These utils exclusively live in Tibanna #
###########################################


def prep_awsem_template(filename, webprod=False, tag=None):
    Tibanna_dir = os.path.dirname(os.path.realpath(__file__)).replace('/core', '')
    template = Tibanna_dir + '/test_json/' + filename
    with open(template, 'r') as f:
        awsem_template = json.load(f)
    # webdev ->webprod
    if webprod:
        awsem_template['output_bucket'] = 'elasticbeanstalk-fourfront-webprod-wfoutput'
        awsem_template['_tibanna']['env'] = 'fourfront-webprod'
        for inb in awsem_template['input_files']:
            inb['bucket_name'] = inb['bucket_name'].replace('webdev', 'webprod')
    if tag:
        awsem_template['tag'] = tag
        clear_awsem_template(awsem_template)
    return awsem_template


def clear_awsem_template(awsem_template):
    """clear awsem template for reuse"""
    if 'response' in awsem_template['_tibanna']:
        del(awsem_template['_tibanna']['response'])
    if 'run_name' in awsem_template['_tibanna'] and len(awsem_template['_tibanna']['run_name']) > 50:
        awsem_template['_tibanna']['run_name'] = awsem_template['_tibanna']['run_name'][:-36]


def rerun(exec_arn, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, override_config=None, app_name_filter=None):
    """rerun a specific job
    override_config : dictionary for overriding config (keys are the keys inside config)
        e.g. override_config = { 'instance_type': 't2.micro' }
    app_name_filter : app_name (e.g. hi-c-processing-pairs), if specified,
    then rerun only if it matches app_name
    """
    client = boto3.client('stepfunctions')
    res = client.describe_execution(executionArn=exec_arn)
    awsem_template = json.loads(res['input'])

    # filter by app_name
    if app_name_filter:
        if 'app_name' not in awsem_template:
            return(None)
        if awsem_template['app_name'] != app_name_filter:
            return(None)

    clear_awsem_template(awsem_template)

    # override config
    if override_config:
        for k, v in override_config.iteritems():
            awsem_template['config'][k] = v

    return(_run_workflow(awsem_template, sfn=sfn))


def rerun_many(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, stopdate='13Feb2018', stophour=13,
               stopminute=0, offset=0, sleeptime=5, status='FAILED',
               override_config=None, app_name_filter=None):
    """Reruns step function jobs that failed after a given time point (stopdate, stophour (24-hour format), stopminute)
    By default, stophour should be the same as your system time zone. This can be changed by setting a different offset.
    If offset=5, for instance, that means your stoptime=12 would correspond to your system time=17.
    Sleeptime is sleep time in seconds between rerun submissions.
    By default, it reruns only 'FAILED' runs, but this can be changed by resetting status.
    examples)
    rerun_many('tibanna_pony-dev')
    rerun_many('tibanna_pony', stopdate= '14Feb2018', stophour=14, stopminute=20)
    """
    stophour = stophour + offset
    stoptime = stopdate + ' ' + str(stophour) + ':' + str(stopminute)
    stoptime_in_datetime = datetime.strptime(stoptime, '%d%b%Y %H:%M')
    client = boto3.client('stepfunctions')
    sflist = client.list_executions(stateMachineArn=STEP_FUNCTION_ARN(sfn), statusFilter=status)
    k = 0
    for exc in sflist['executions']:
        print(exc['stopDate'].replace(tzinfo=None))
        print(stoptime_in_datetime)
        if exc['stopDate'].replace(tzinfo=None) > stoptime_in_datetime:
            k = k + 1
            rerun(exc['executionArn'], sfn=sfn,
                  override_config=override_config, app_name_filter=app_name_filter)
            time.sleep(sleeptime)


def kill_all(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    """killing all the running jobs"""
    client = boto3.client('stepfunctions')
    stateMachineArn = STEP_FUNCTION_ARN(sfn)
    sflist = client.list_executions(stateMachineArn=stateMachineArn, statusFilter='RUNNING')
    for exc in sflist['executions']:
        client.stop_execution(executionArn=exc['executionArn'], error="Aborted")
