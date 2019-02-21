# -*- coding: utf-8 -*-
import os
import errno
import sys
import time
import json
from invoke import task, run
import boto3
import contextlib
import shutil
# from botocore.errorfactory import ExecutionAlreadyExists
from core.ec2_utils import AWS_S3_ROLE_NAME
from core.utils import create_jobid
from core.utils import AWS_REGION, AWS_ACCOUNT_NUMBER
from core.utils import TIBANNA_DEFAULT_STEP_FUNCTION_NAME, STEP_FUNCTION_ARN
from core.utils import run_workflow as _run_workflow
from core.utils import create_stepfunction as _create_stepfunction
from core.utils import _tibanna
from core.launch_utils import rerun as _rerun
from core.launch_utils import rerun_many as _rerun_many
from core.utils import kill as _kill
from core.utils import log as _log
from core.utils import kill_all as _kill_all
from core.iam_utils import create_tibanna_iam
from core.iam_utils import get_ec2_role_name, get_lambda_role_name
from contextlib import contextmanager
import aws_lambda
import requests
import random

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
POSITIVE = 'https://gist.github.com/j1z0/bbed486d85fb4d64825065afbfb2e98f/raw/positive.txt'
NEGATIVE = 'https://gist.github.com/j1z0/bbed486d85fb4d64825065afbfb2e98f/raw/negative.txt'
AMI_ID_CWL_V1 = 'ami-0f06a8358d41c4b9c'
AMI_ID_CWL_DRAFT3 = 'ami-0f06a8358d41c4b9c'
AMI_ID_WDL = 'ami-0f06a8358d41c4b9c'
TIBANNA_REPO_NAME = os.environ.get('TIBANNA_REPO_NAME', '4dn-dcic/tibanna')
TIBANNA_REPO_BRANCH = os.environ.get('TIBANNA_REPO_BRANCH', 'master')
TIBANNA_PROFILE_ACCESS_KEY = os.environ.get('TIBANNA_PROFILE_ACCESS_KEY', '')
TIBANNA_PROFILE_SECRET_KEY = os.environ.get('TIBANNA_PROFILE_SECRET_KEY', '')
UNICORN_LAMBDAS = ['run_task_awsem', 'check_task_awsem']


def get_random_line_in_gist(url):
    listing = requests.get(url)
    return random.choice(listing.text.split("\n"))


def play(ctx, positive=False):
    type_url = POSITIVE if positive else NEGATIVE
    # no spaces in url
    media_url = '%20'.join(get_random_line_in_gist(type_url).split())
    run("vlc -I rc %s --play-and-exit -q" % (media_url))


@contextmanager
def setenv(**kwargs):
    # Backup
    prev = {}
    for k, v in kwargs.items():
        if k in os.environ:
            prev[k] = os.environ[k]
        os.environ[k] = v

    yield

    # Restore
    for k in kwargs.keys():
        if k in prev:
            os.environ[k] = prev[k]
        else:
            del os.environ[k]


def get_all_core_lambdas():
    return [
        'validate_md5_s3_trigger',
        'validate_md5_s3_initiator',
        'start_run_awsem',
        'run_task_awsem',
        'check_task_awsem',
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
                           'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER,
                           'AWS_S3_ROLE_NAME': AWS_S3_ROLE_NAME},
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


@contextlib.contextmanager
def chdir(dirname=None):
    curdir = os.getcwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
            yield
    finally:
        os.chdir(curdir)


def upload(keyname, data, s3bucket, secret=None):
    # don't set this as a global, since not all tasks require it
    if secret is None:
        secret = os.environ.get("SECRET")
        if secret is None:
            raise RuntimeError("SECRET should be defined in env")

    s3 = boto3.client('s3')
    s3.put_object(Bucket=s3bucket,
                  Key=keyname,
                  Body=data,
                  SSECustomerKey=secret,
                  SSECustomerAlgorithm='AES256')


def copytree(src, dst, symlinks=False, ignore=None):
    skipfiles = ['.coverage', 'dist', 'htmlcov', '__init__.pyc', 'coverage.xml', 'service.pyc']
    for item in os.listdir(src):
        src_file = os.path.join(src, item)
        dst_file = os.path.join(dst, item)
        if src_file.split('/')[-1] in skipfiles:
            print("skipping file %s" % src_file)
            continue
        if os.path.isdir(src_file):
            mkdir(dst_file)
            shutil.copytree(src_file, dst_file, symlinks, ignore)
        else:
            shutil.copy2(src_file, dst_file)


def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


@task
def test(ctx, watch=False, last_failing=False, no_flake=False, k='',  extra='',
         ignore='', ignore_pony=False, ignore_webdev=False):
    """Run the tests.
    Note: --watch requires pytest-xdist to be installed.
    """
    import pytest
    if not no_flake:
        flake()
    args = ['-rxs', ]
    if k:
        args.append('-k %s' % k)
    args.append(extra)
    if watch:
        args.append('-f')
    else:
        args.append('--cov-report')
        args.append('xml')
        args.append('--cov-report')
        args.append('html')
    if last_failing:
        args.append('--lf')
    if ignore:
        args.append('--ignore')
        args.append(ignore)
    if ignore_pony:
        args.append('--ignore')
        args.append('tests/core/pony')
    if ignore_webdev:
        args.append('--ignore')
        args.append('tests/core/pony/test_webdev.py')
    retcode = pytest.main(args)
    try:
        good = True if retcode == 0 else False
        play(ctx, good)
    except:
        print("install vlc for more exciting test runs...")
    if retcode != 0:
        print("test failed exiting")
        sys.exit(retcode)
    return retcode


def flake():
    """Run flake8 on codebase."""
    run('flake8 .', echo=True)
    print("flake8 passed!!!")


def clean():
    run("rm -rf build")
    run("rm -rf dist")
    print("Cleaned up.")


@task
def deploy_core(ctx, name, tests=False, suffix=None, usergroup=None):
    """deploy/update lambdas only"""
    print("preparing for deploy...")
    if tests:
        print("running tests...")
        if test(ctx) != 0:
            print("tests need to pass first before deploy")
            return
    else:
        print("skipping tests. execute with --tests flag to run them")
    if name == 'all':
        names = get_all_core_lambdas()

    elif name == 'unicorn':
        names = UNICORN_LAMBDAS
    else:
        names = [name, ]
    print('deploying the following lambdas: %s' % names)

    # dist directores are the enemy, clean them all
    for name in get_all_core_lambdas():
        print("cleaning house before deploying")
        with chdir("./core/%s" % (name)):
            clean()

    for name in names:
        print("=" * 20, "Deploying lambda", name, "=" * 20)
        with chdir("./core/%s" % (name)):
            print("clean up previous builds.")
            clean()
            print("building lambda package")
            deploy_lambda_package(ctx, name, suffix=suffix, usergroup=usergroup)
            # need to clean up all dist, otherwise, installing local package takes forever
            clean()


def deploy_lambda_package(ctx, name, suffix=None, usergroup=None):
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
    if name in UNICORN_LAMBDAS:
        requirements_file = '../../requirements-lambda-unicorn.txt'
    else:
        requirements_file = '../../requirements-lambda-pony.txt'
    with chdir(new_src):
        aws_lambda.deploy(os.getcwd(), local_package='../..', requirements=requirements_file)
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
            lambda_update_config['Environment']['Variables']['AWS_S3_ROLE_NAME'] = 'S3_access'  # 4dn-dcic default(temp)
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


def _PROD():
    return _tbenv() == 'PROD'


def _tbenv(env_data=None):
    if env_data and env_data.get('env'):
        return env_data('env')
    return os.environ.get('ENV_NAME')


@task
def run_workflow(ctx, input_json='', sfn='', jobid=''):
    """run a workflow"""
    if not jobid:
        jobid = create_jobid()
    with open(input_json) as input_file:
        data = json.load(input_file)
        if sfn == '':
            resp = _run_workflow(data, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, jobid=jobid)
        else:
            resp = _run_workflow(data, sfn=sfn, jobid=jobid)
        print("JOBID %s submitted" % resp['jobid'])
        print("EXECUTION ARN = %s" % resp[_tibanna]['exec_arn'])
        if 'cloudwatch_dashboard' in resp['config'] and resp['config']['cloudwatch_dashboard']:
            cw_db_url = 'https://console.aws.amazon.com/cloudwatch/' + \
                'home?region=%s#dashboards:name=awsem-%s' % (AWS_REGION, jobid)
            print("Cloudwatch Dashboard = %s" % cw_db_url)
        run('open %s' % resp[_tibanna]['url'])


@task
def setup_tibanna_env(ctx, buckets='', usergroup_tag='default', no_randomize=False, verbose=False):
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


@task
def deploy_tibanna(ctx, suffix=None, sfn_type='pony', usergroup=None, tests=False,
                   setup=False, buckets='', setenv=False):
    """deploy tibanna unicorn or pony to AWS cloud (pony is for 4DN-DCIC only)"""
    if setup:
        if usergroup:
            usergroup = setup_tibanna_env(ctx, buckets, usergroup, True)
        else:
            usergroup = setup_tibanna_env(ctx, buckets)  # override usergroup
    print("creating a new step function...")
    if sfn_type not in ['pony', 'unicorn']:
        raise Exception("Invalid sfn_type : it must be either pony or unicorn.")
    # this function will remove existing step function on a conflict
    res = _create_stepfunction(suffix, sfn_type, usergroup=usergroup)
    print(res.get('stateMachineArn').split(':'))
    step_function_name = res.get('stateMachineArn').split(':')[6]
    if setenv:
        os.environ['TIBANNA_DEFAULT_STEP_FUNCTION_NAME'] = step_function_name
        with open(os.getenv('HOME') + "/.bashrc", "a") as outfile:  # 'a' stands for "append"
            outfile.write("\nexport TIBANNA_DEFAULT_STEP_FUNCTION_NAME=%s\n" % step_function_name)
    print(res)
    print("deploying lambdas...")
    if sfn_type == 'pony':
        deploy_core(ctx, 'all', tests=tests, suffix=suffix, usergroup=usergroup)
    else:
        deploy_core(ctx, 'unicorn', tests=tests, suffix=suffix, usergroup=usergroup)
    return step_function_name


@task
def deploy_unicorn(ctx, suffix=None, no_setup=False, buckets='',
                   no_setenv=False, usergroup=None):
    """deploy tibanna unicorn to AWS cloud"""
    deploy_tibanna(ctx, suffix=suffix, sfn_type='unicorn',
                   tests=False, usergroup=usergroup, setup=not no_setup,
                   buckets=buckets, setenv=not no_setenv)


@task
def add_user(ctx, user, usergroup):
    """add a user to a tibanna group"""
    boto3.client('iam').add_user_to_group(
        GroupName='tibanna_' + usergroup,
        UserName=user
    )


@task
def users(ctx):
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


@task
def list(ctx, numbers=False, sfn_type="unicorn"):
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


@task
def rerun(ctx, exec_arn, sfn='tibanna_pony',
          instance_type=None, shutdown_min=None, ebs_size=None, ebs_type=None, ebs_iops=None,
          overwrite_input_extra=None, key_name=None, name=None):
    """ rerun a specific job"""
    override_config = dict()
    if instance_type:
        override_config['instance_type'] = instance_type
    if shutdown_min:
        override_config['shutdown_min'] = shutdown_min
    if ebs_size:
        override_config['ebs_size'] = int(ebs_size)
    if overwrite_input_extra:
        override_config['overwrite_input_extra'] = overwrite_input_extra
    if key_name:
        override_config['key_name'] = key_name
    if ebs_type:
        override_config['ebs_type'] = ebs_type
        if ebs_type == 'gp2':
            override_config['ebs_iops'] = ''
    if ebs_iops:
        override_config['ebs_iops'] = ebs_iops
    _rerun(exec_arn, sfn=sfn, override_config=override_config, name=name)


@task
def log(ctx, exec_arn=None, job_id=None, exec_name=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, p=False):
    """print execution log or postrun json (-p) for a job"""
    print(_log(exec_arn, job_id, exec_name, sfn, p))


@task
def kill_all(ctx, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    """kill all the running jobs on a step function"""
    _kill_all(sfn)


@task
def kill(ctx, exec_arn=None, job_id=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    """kill a specific job"""
    _kill(exec_arn, job_id, sfn)


@task
def rerun_many(ctx, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, stopdate='13Feb2018', stophour=13,
               stopminute=0, offset=0, sleeptime=5, status='FAILED'):
    """rerun all the jobs that failed after a given time point
    filtered by the time when the run failed (stopdate, stophour (24-hour format), stopminute)
    By default, stophour should be the same as your system time zone. This can be changed by setting a different offset.
    If offset=5, for instance, that means your stoptime=12 would correspond to your system time=17.
    Sleeptime is sleep time in seconds between rerun submissions.
    By default, it reruns only 'FAILED' runs, but this can be changed by resetting status.

    Examples

    rerun_many('tibanna_pony-dev')
    rerun_many('tibanna_pony', stopdate= '14Feb2018', stophour=14, stopminute=20)
    """
    _rerun_many(sfn=sfn, stopdate=stopdate, stophour=stophour,
                stopminute=stopminute, offset=offset, sleeptime=sleeptime, status=status)


@task
def stat(ctx, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, status=None, verbose=False):
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
                print("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(jobid, status, name, start_time, stop_time,
                                                                          instance_id, instance_type, instance_status,
                                                                          instance_ip, keyname, password))
            else:
                print("{}\t{}\t{}\t{}\t{}".format(jobid, status, name, start_time, stop_time))
        if 'nextToken' in res:
            res = client.list_executions(nextToken=res['nextToken'], **args)
        else:
            break
