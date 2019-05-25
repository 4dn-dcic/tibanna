# -*- coding: utf-8 -*-
import os
import time
import json
import boto3
import contextlib
import importlib
from invoke import run
# from botocore.errorfactory import ExecutionAlreadyExists
from tibanna.vars import (
    AWS_REGION,
    AWS_ACCOUNT_NUMBER,
    AMI_ID_CWL_V1,
    AMI_ID_CWL_DRAFT3,
    AMI_ID_WDL,
    TIBANNA_REPO_NAME,
    TIBANNA_REPO_BRANCH,
    TIBANNA_PROFILE_ACCESS_KEY,
    TIBANNA_PROFILE_SECRET_KEY,
    AWS_S3_ROLE_NAME
)
from tibanna.iam_utils import (
    create_tibanna_iam,
    get_stepfunction_role_name,
    get_ec2_role_name,
    get_lambda_role_name,
)
from tibanna.test_utils import test
from tibanna import lambdas as unicorn_lambdas
from tibanna_4dn import lambdas as pony_lambdas
from contextlib import contextmanager
import aws_lambda


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
