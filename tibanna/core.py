# -*- coding: utf-8 -*-
import os
import boto3
import json
import time
import copy
import logging
import importlib
from datetime import datetime
from uuid import uuid4, UUID
from invoke import run
from .vars import (
    _tibanna,
    AWS_ACCOUNT_NUMBER,
    AWS_REGION,
    TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
    DYNAMODB_TABLE,
    STEP_FUNCTION_ARN,
    EXECUTION_ARN,
    AMI_ID_CWL_V1,
    AMI_ID_CWL_DRAFT3,
    AMI_ID_WDL,
    TIBANNA_REPO_NAME,
    TIBANNA_REPO_BRANCH,
    TIBANNA_PROFILE_ACCESS_KEY,
    TIBANNA_PROFILE_SECRET_KEY,
)
from tibanna.utils import (
    _tibanna_settings,
    printlog,
    create_jobid
)
# from botocore.errorfactory import ExecutionAlreadyExists
from tibanna.iam_utils import (
    create_tibanna_iam,
    get_stepfunction_role_name,
    get_ec2_role_name,
    get_lambda_role_name,
)
from .test_utils import test
from . import lambdas as lambdas_module
from contextlib import contextmanager
import aws_lambda


# logger
LOG = logging.getLogger(__name__)


def randomize_run_name(run_name, sfn):
    arn = EXECUTION_ARN(run_name, sfn)
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
    arn = EXECUTION_ARN(run_name, sfn)
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


def log(exec_arn=None, job_id=None, exec_name=None,
        sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, postrunjson=False):
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


def stat(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, status=None, verbose=False):
    """print out executions with details (-v)
    status can be one of 'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'
    """
    args = {
        'stateMachineArn': STEP_FUNCTION_ARN(sfn),
        'maxResults': 100
    }
    if status:
        args['statusFilter'] = status
    res = dict()
    client = boto3.client('stepfunctions')
    if verbose:
        print("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format('jobid', 'status', 'name',
                                                                  'start_time', 'stop_time',
                                                                  'instance_id', 'instance_type',
                                                                  'instance_status', 'ip', 'key',
                                                                  'password'))
    else:
        print("{}\t{}\t{}\t{}\t{}".format('jobid', 'status', 'name', 'start_time', 'stop_time'))
    res = client.list_executions(**args)
    ec2 = boto3.client('ec2')
    while True:
        if 'executions' not in res or not res['executions']:
            break
        for exc in res['executions']:
            desc = client.describe_execution(executionArn=exc['executionArn'])
            jobid = json.loads(desc['input']).get('jobid', 'no jobid')
            status = exc['status']
            name = exc['name']
            start_time = exc['startDate'].strftime("%Y-%m-%d %H:%M")
            if 'stopDate' in exc:
                stop_time = exc['stopDate'].strftime("%Y-%m-%d %H:%M")
            else:
                stop_time = ''
            if verbose:
                # collect instance stats
                res = ec2.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': ['awsem-' + jobid]}])
                if res['Reservations']:
                    instance_status = res['Reservations'][0]['Instances'][0]['State']['Name']
                    instance_id = res['Reservations'][0]['Instances'][0]['InstanceId']
                    instance_type = res['Reservations'][0]['Instances'][0]['InstanceType']
                    if instance_status not in ['terminated', 'shutting-down']:
                        instance_ip = res['Reservations'][0]['Instances'][0].get('PublicIpAddress', '-')
                        keyname = res['Reservations'][0]['Instances'][0].get('KeyName', '-')
                        password = json.loads(desc['input'])['config'].get('password', '-')
                    else:
                        instance_ip = '-'
                        keyname = '-'
                        password = '-'
                else:
                    instance_status = '-'
                    instance_id = '-'
                    instance_type = '-'
                    instance_ip = '-'
                    keyname = '-'
                    password = '-'
                print_template = "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}"
                print(print_template.format(jobid, status, name, start_time, stop_time,
                                            instance_id, instance_type, instance_status,
                                            instance_ip, keyname, password))
            else:
                print("{}\t{}\t{}\t{}\t{}".format(jobid, status, name, start_time, stop_time))
        if 'nextToken' in res:
            res = client.list_executions(nextToken=res['nextToken'], **args)
        else:
            break


def list_sfns(numbers=False, sfn_type="unicorn"):
    """list all step functions, optionally with a summary (-n)"""
    st = boto3.client('stepfunctions')
    res = st.list_state_machines(
        maxResults=1000
    )
    header = "name\tcreation_date"
    if numbers:
        header = header + "\trunning\tsucceeded\tfailed\taborted\ttimed_out"
    print(header)
    for s in res['stateMachines']:
        if not s['name'].startswith('tibanna_' + sfn_type):
            continue
        line = "%s\t%s" % (s['name'], str(s['creationDate']))
        if numbers:
            counts = count_status(s['stateMachineArn'], st)
            for status in ['RUNNING', 'SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED_OUT']:
                line = line + "\t%i" % counts[status]
        print(line)


def count_status(sfn_arn, client):
        next_token = None
        count = dict()
        while True:
            args = {'stateMachineArn': sfn_arn,
                    # 'statusFilter': status,
                    'maxResults': 1000}
            if next_token:
                args['nextToken'] = next_token
            res = client.list_executions(**args)
            for status in ['RUNNING', 'SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED_OUT']:
                count[status] = count.get(status, 0) + sum([r['status'] == status for r in res['executions']])
            if res.get('nextToken', ''):
                next_token = res['nextToken']
            else:
                break
        return count


def prep_input_json_template(filename, webprod=False, tag=None):
    Tibanna_dir = os.path.dirname(os.path.realpath(__file__)).replace('/tibanna', '')
    template = Tibanna_dir + '/test_json/' + filename
    with open(template, 'r') as f:
        input_json_template = json.load(f)
    # webdev ->webprod
    if webprod:
        input_json_template['output_bucket'] = 'elasticbeanstalk-fourfront-webprod-wfoutput'
        input_json_template['_tibanna']['env'] = 'fourfront-webprod'
        for inb in input_json_template['input_files']:
            inb['bucket_name'] = inb['bucket_name'].replace('webdev', 'webprod')
    if tag:
        input_json_template['tag'] = tag
        clear_input_json_template(input_json_template)
    return input_json_template


def clear_input_json_template(input_json_template):
    """clear awsem template for reuse"""
    if 'response' in input_json_template['_tibanna']:
        del(input_json_template['_tibanna']['response'])
    if 'run_name' in input_json_template['_tibanna'] and len(input_json_template['_tibanna']['run_name']) > 40:
        input_json_template['_tibanna']['run_name'] = input_json_template['_tibanna']['run_name'][:-36]
        input_json_template['config']['run_name'] = input_json_template['_tibanna']['run_name']


def rerun(exec_arn, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
          override_config=None, app_name_filter=None, name=None):
    """rerun a specific job
    override_config : dictionary for overriding config (keys are the keys inside config)
        e.g. override_config = { 'instance_type': 't2.micro' }
    app_name_filter : app_name (e.g. hi-c-processing-pairs), if specified,
    then rerun only if it matches app_name
    """
    client = boto3.client('stepfunctions')
    res = client.describe_execution(executionArn=exec_arn)
    input_json_template = json.loads(res['input'])
    # filter by app_name
    if app_name_filter:
        if 'app_name' not in input_json_template:
            return(None)
        if input_json_template['app_name'] != app_name_filter:
            return(None)
    clear_input_json_template(input_json_template)
    # override config
    if override_config:
        for k, v in iter(override_config.items()):
            input_json_template['config'][k] = v
    return(run_workflow(input_json_template, sfn=sfn))


def rerun_many(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, stopdate='13Feb2018', stophour=13,
               stopminute=0, offset=0, sleeptime=5, status='FAILED',
               override_config=None, app_name_filter=None):
    """Reruns step function jobs that failed after a given time point
    (stopdate, stophour (24-hour format), stopminute)
    By default, stophour should be the same as your system time zone.
    This can be changed by setting a different offset.
    If offset=5, for instance, that means your stoptime=12 would correspond
    to your system time=17. Sleeptime is sleep time in seconds between rerun submissions.
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


UNICORN_LAMBDAS = ['run_task_awsem', 'check_task_awsem']


def get_pony_only_tibanna_lambdas():
    return [
        'validate_md5_s3_trigger',
        'validate_md5_s3_initiator',
        'start_run_awsem',
        'update_ffmeta_awsem',
        'run_workflow',
    ]


def env_list(name):
    # don't set this as a global, since not all tasks require it
    secret = os.environ.get("SECRET", '')
    envlist = {
        'run_workflow': {'SECRET': secret,
                         'TIBANNA_AWS_REGION': AWS_REGION,
                         'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
        'start_run_awsem': {'SECRET': secret,
                            'TIBANNA_AWS_REGION': AWS_REGION,
                            'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
        'run_task_awsem': {'AMI_ID_CWL_V1': AMI_ID_CWL_V1,
                           'AMI_ID_CWL_DRAFT3': AMI_ID_CWL_DRAFT3,
                           'AMI_ID_WDL': AMI_ID_WDL,
                           'TIBANNA_REPO_NAME': TIBANNA_REPO_NAME,
                           'TIBANNA_REPO_BRANCH': TIBANNA_REPO_BRANCH,
                           'TIBANNA_AWS_REGION': AWS_REGION,
                           'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
        'check_task_awsem': {'TIBANNA_AWS_REGION': AWS_REGION,
                             'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
        'update_ffmeta_awsem': {'SECRET': secret,
                                'TIBANNA_AWS_REGION': AWS_REGION,
                                'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
        'validate_md5_s3_initiator': {'SECRET': secret,
                                      'TIBANNA_AWS_REGION': AWS_REGION,
                                      'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER}
    }
    if TIBANNA_PROFILE_ACCESS_KEY and TIBANNA_PROFILE_SECRET_KEY:
        envlist['run_task_awsem'].update({
            'TIBANNA_PROFILE_ACCESS_KEY': TIBANNA_PROFILE_ACCESS_KEY,
            'TIBANNA_PROFILE_SECRET_KEY': TIBANNA_PROFILE_SECRET_KEY}
        )
    return envlist.get(name, '')


@contextmanager
def chdir(dirname=None):
    curdir = os.getcwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
            yield
    finally:
        os.chdir(curdir)


def clean():
    run("rm -rf build")
    run("rm -rf dist")
    print("Cleaned up.")


def deploy_lambda(name, suffix, dev, usergroup):
    """
    deploy a single lambda using the aws_lambda.deploy_tibanna (BETA)
    """
    if name not in dir(lambdas_module):
        raise Exception("Could not find lambda function file for %s" % name)
    lambda_fxn_module = importlib.import_module('.'.join([lambdas_module.__name__,  name]))
    requirements_fpath = os.path.join(lambdas_module.__path__[0], 'requirements.txt')
    # add extra config to the lambda deployment
    extra_config = {}
    envs = env_list(name)
    if envs:
        extra_config['Environment'] = {'Variables': envs}
    if name == 'run_task_awsem':
        if usergroup:
            extra_config['Environment']['Variables']['AWS_S3_ROLE_NAME'] \
                = get_ec2_role_name('tibanna_' + usergroup)
        else:
            extra_config['Environment']['Variables']['AWS_S3_ROLE_NAME'] = 'S3_access'  # 4dn-dcic default(temp)
    # add role
    print('name=%s' % name)
    if name in ['run_task_awsem', 'check_task_awsem']:
        role_arn_prefix = 'arn:aws:iam::' + AWS_ACCOUNT_NUMBER + ':role/'
        if usergroup:
            role_arn = role_arn_prefix + get_lambda_role_name('tibanna_' + usergroup, name)
        else:
            role_arn = role_arn_prefix + 'lambda_full_s3'  # 4dn-dcic default(temp)
            print(role_arn)
        extra_config['Role'] = role_arn
    # install the python pkg in the current working directory if --dev is set
    local_pkg = '.' if dev else None
    aws_lambda.deploy_tibanna(lambda_fxn_module, suffix, requirements_fpath, extra_config, local_pkg)


def deploy_packaged_lambdas(name, suffix=None, dev=False, usergroup=None):
    if name == 'pony_only':
        names = get_pony_only_tibanna_lambdas()
    elif name == 'unicorn':
        names = UNICORN_LAMBDAS
    else:
        names = [name, ]
    for name in names:
        deploy_lambda(name, suffix, dev, usergroup)


def deploy_core(name, tests=False, suffix=None, usergroup=None, package='tibanna'):
    """deploy/update lambdas only"""
    print("preparing for deploy...")
    if tests:
        print("running tests...")
        if test() != 0:
            print("tests need to pass first before deploy")
            return
    else:
        print("skipping tests. execute with --tests flag to run them")
    if name == 'pony_only':
        names = get_pony_only_tibanna_lambdas()
    elif name == 'unicorn':
        names = UNICORN_LAMBDAS
    else:
        names = [name, ]
    print('deploying the following lambdas: %s' % names)
    for name in names:
        print("=" * 20, "Deploying lambda", name, "=" * 20)
        with chdir(package + "/lambdas/%s" % (name)):
            print("clean up previous builds.")
            # dist directores are the enemy, clean them all
            clean()
            print("building lambda package")
            deploy_lambda_package(name, suffix=suffix, usergroup=usergroup, package=package)
            # need to clean up all dist, otherwise, installing local package takes forever
            clean()


def deploy_lambda_package(name, suffix=None, usergroup=None, package='tibanna'):
    # create the temporary local dev lambda directories
    if usergroup:
        if suffix:
            suffix = usergroup + suffix
        else:
            suffix = usergroup
    if suffix:
        new_name = name + '_' + suffix
        new_src = '../' + new_name
        cmd_mkdir = "rm -fr %s; mkdir -p %s" % (new_src, new_src)
        cmd_copy = "cp -r * %s" % new_src
        cmd_cd = "cd %s" % new_src
        cmd_modify_cfg = "sed 's/%s/%s/g' config.yaml > config.yaml#" % (name, new_name)
        cmd_replace_cfg = "mv config.yaml# config.yaml"
        cmd = ';'.join([cmd_mkdir, cmd_copy, cmd_cd, cmd_modify_cfg, cmd_replace_cfg])
        print(cmd)
        run(cmd)
    else:
        new_name = name
        new_src = '../' + new_name
    # use the lightweight requirements for the lambdas to simplify deployment
    # if name in UNICORN_LAMBDAS:
    #     requirements_file = package + '/lambdas/requirements-lambda-unicorn.txt'
    # else:
    #     requirements_file = package + '/lambdas/requirements-lambda-pony.txt'
    requirements_file = '../requirements.txt'
    with chdir(new_src):
        aws_lambda.deploy(os.getcwd(), local_package=package + '/lambdas', requirements=requirements_file)
    # add environment variables
    lambda_update_config = {'FunctionName': new_name}
    envs = env_list(name)
    if envs:
        lambda_update_config['Environment'] = {'Variables': envs}
    if name == 'run_task_awsem':
        if usergroup:
            lambda_update_config['Environment']['Variables']['AWS_S3_ROLE_NAME'] \
                = get_ec2_role_name('tibanna_' + usergroup)
        else:
            lambda_update_config['Environment']['Variables']['AWS_S3_ROLE_NAME'] \
                = 'S3_access'  # 4dn-dcic default(temp)
    # add role
    print('name=%s' % name)
    if name in ['run_task_awsem', 'check_task_awsem']:
        role_arn_prefix = 'arn:aws:iam::' + AWS_ACCOUNT_NUMBER + ':role/'
        if usergroup:
            role_arn = role_arn_prefix + get_lambda_role_name('tibanna_' + usergroup, name)
        else:
            role_arn = role_arn_prefix + 'lambda_full_s3'  # 4dn-dcic default(temp)
            print(role_arn)
        lambda_update_config['Role'] = role_arn
    client = boto3.client('lambda')
    resp = client.update_function_configuration(**lambda_update_config)
    print(resp)
    # delete the temporary local dev lambda directories
    if suffix:
        old_src = '../' + name
        run('cd %s; rm -rf %s' % (old_src, new_src))


def setup_tibanna_env(buckets='', usergroup_tag='default', no_randomize=False, verbose=False):
    """set up usergroup environment on AWS
    This function is called automatically by deploy_tibanna or deploy_unicorn
    Use it only when the IAM permissions need to be reset"""
    print("setting up tibanna usergroup environment on AWS...")
    if not AWS_ACCOUNT_NUMBER or not AWS_REGION:
        print("Please set and export environment variable AWS_ACCOUNT_NUMBER and AWS_REGION!")
        exit(1)
    if not buckets:
        print("WARNING: Without setting buckets (using --buckets)," +
              "Tibanna would have access to only public buckets." +
              "To give permission to Tibanna for private buckets," +
              "use --buckets=<bucket1>,<bucket2>,...")
        time.sleep(2)
    if buckets:
        bucket_names = buckets.split(',')
    else:
        bucket_names = None
    tibanna_policy_prefix = create_tibanna_iam(AWS_ACCOUNT_NUMBER, bucket_names,
                                               usergroup_tag, AWS_REGION, no_randomize=no_randomize,
                                               verbose=verbose)
    tibanna_usergroup = tibanna_policy_prefix.replace("tibanna_", "")
    print("Tibanna usergroup %s has been created on AWS." % tibanna_usergroup)
    return tibanna_usergroup


def deploy_tibanna(suffix=None, sfn_type='pony', usergroup=None, tests=False,
                   setup=False, buckets='', setenv=False):
    """deploy tibanna unicorn or pony to AWS cloud (pony is for 4DN-DCIC only)"""
    if setup:
        if usergroup:
            usergroup = setup_tibanna_env(buckets, usergroup, True)
        else:
            usergroup = setup_tibanna_env(buckets)  # override usergroup
    print("creating a new step function...")
    if sfn_type not in ['pony', 'unicorn']:
        raise Exception("Invalid sfn_type : it must be either pony or unicorn.")
    # this function will remove existing step function on a conflict
    step_function_name = create_stepfunction(suffix, sfn_type, usergroup=usergroup)
    if setenv:
        os.environ['TIBANNA_DEFAULT_STEP_FUNCTION_NAME'] = step_function_name
        with open(os.getenv('HOME') + "/.bashrc", "a") as outfile:  # 'a' stands for "append"
            outfile.write("\nexport TIBANNA_DEFAULT_STEP_FUNCTION_NAME=%s\n" % step_function_name)
    print("deploying lambdas...")
    if sfn_type == 'pony':
        deploy_core('pony_only', tests=tests, suffix=suffix, usergroup=usergroup, package='tibanna_4dn')
        deploy_core('unicorn', tests=tests, suffix=suffix, usergroup=usergroup)
    else:
        deploy_core('unicorn', tests=tests, suffix=suffix, usergroup=usergroup)
    return step_function_name


def deploy_unicorn(suffix=None, no_setup=False, buckets='',
                   no_setenv=False, usergroup=None):
    """deploy tibanna unicorn to AWS cloud"""
    deploy_tibanna(suffix=suffix, sfn_type='unicorn',
                   tests=False, usergroup=usergroup, setup=not no_setup,
                   buckets=buckets, setenv=not no_setenv)


def add_user(user, usergroup):
    """add a user to a tibanna group"""
    boto3.client('iam').add_user_to_group(
        GroupName='tibanna_' + usergroup,
        UserName=user
    )


def users():
    """list all users along with their associated tibanna user groups"""
    client = boto3.client('iam')
    marker = None
    while True:
        if marker:
            res = client.list_users(Marker=marker)
        else:
            res = client.list_users()
        print("user\ttibanna_usergroup")
        for r in res['Users']:
            res_groups = client.list_groups_for_user(
                UserName=r['UserName']
            )
            groups = [rg['GroupName'] for rg in res_groups['Groups']]
            groups = filter(lambda x: 'tibanna_' in x, groups)
            groups = [x.replace('tibanna_', '') for x in groups]
            print("%s\t%s" % (r['UserName'], ','.join(groups)))
        marker = res.get('Marker', '')
        if not marker:
            break


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
      "Comment": "Start a workflow run on awsem, track it and update our metadata to reflect whats going on",
      "StartAt": sfn_start_lambda[sfn_type],
      "States": sfn_state_defs[sfn_type]
    }
    # if this encouters an existing step function with the same name, delete
    sfn = boto3.client('stepfunctions', region_name=region_name)
    retries = 12  # wait 10 seconds between retries for total of 120s
    for i in range(retries):
        try:
            sfn.create_state_machine(
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
                sfn.update_state_machine(
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
