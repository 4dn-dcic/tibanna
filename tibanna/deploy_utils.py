# -*- coding: utf-8 -*-
import os
import errno
import sys
import time
import json
import boto3
import contextlib
import shutil
import importlib
from invoke import run
# from botocore.errorfactory import ExecutionAlreadyExists
from tibanna.ec2_utils import AWS_S3_ROLE_NAME
from tibanna.utils import AWS_REGION, AWS_ACCOUNT_NUMBER
from tibanna.utils import TIBANNA_DEFAULT_STEP_FUNCTION_NAME, STEP_FUNCTION_ARN
from tibanna.utils import create_stepfunction as _create_stepfunction
from tibanna.iam_utils import create_tibanna_iam
from tibanna.iam_utils import get_ec2_role_name, get_lambda_role_name
from tibanna import lambdas as unicorn_lambdas
from tibanna_4dn import lambdas as pony_lambdas
from contextlib import contextmanager
import aws_lambda


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


def test(watch=False, last_failing=False, no_flake=False, k='',  extra='',
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
        args.append('tests/tibanna/pony')
    if ignore_webdev:
        args.append('--ignore')
        args.append('tests/tibanna/pony/test_webdev.py')
    retcode = pytest.main(args)
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


def deploy_lambda(name, suffix, dev, usergroup):
    """
    deploy a single lambda using the aws_lambda.deploy_tibanna (BETA)
    """
    if name in dir(unicorn_lambdas):
        lambdas_module = unicorn_lambdas
    elif name in dir(pony_lambdas):
        lambdas_module = pony_lambdas
    else:
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
    step_function_name = _create_stepfunction(suffix, sfn_type, usergroup=usergroup)
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
                print("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(jobid, status, name, start_time, stop_time,
                                                                          instance_id, instance_type, instance_status,
                                                                          instance_ip, keyname, password))
            else:
                print("{}\t{}\t{}\t{}\t{}".format(jobid, status, name, start_time, stop_time))
        if 'nextToken' in res:
            res = client.list_executions(nextToken=res['nextToken'], **args)
        else:
            break
