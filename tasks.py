# -*- coding: utf-8 -*-
import json
from invoke import task, run
# from botocore.errorfactory import ExecutionAlreadyExists
from tibanna.utils import create_jobid
from tibanna.utils import AWS_REGION
from tibanna.utils import TIBANNA_DEFAULT_STEP_FUNCTION_NAME
from tibanna.utils import run_workflow as _run_workflow
from tibanna.utils import _tibanna
from tibanna.launch_utils import rerun as _rerun
from tibanna.launch_utils import rerun_many as _rerun_many
from tibanna.utils import kill as _kill
from tibanna.utils import log as _log
from tibanna.utils import kill_all as _kill_all
from tibanna.deploy_utils import deploy_core as _deploy_core
from tibanna.deploy_utils import deploy_unicorn as _deploy_unicorn
from tibanna.deploy_utils import deploy_tibanna as _deploy_tibanna
from tibanna.deploy_utils import users as _users
from tibanna.deploy_utils import list_sfns as _list_sfns
from tibanna.deploy_utils import add_user as _add_user
from tibanna.deploy_utils import stat as _stat
from tibanna.deploy_utils import setup_tibanna_env as _setup_tibanna_env
from tibanna.deploy_utils import test as _test


@task
def test(ctx, watch=False, last_failing=False, no_flake=False, k='',  extra='',
         ignore='', ignore_pony=False, ignore_webdev=False):
    """Run the tests.
    Note: --watch requires pytest-xdist to be installed.
    """
    _test(watch=watch, last_failing=last_failing, no_flake=no_flake, k=k,
          extra=extra, ignore=ignore, ignore_pony=ignore_pony, ignore_webdev=ignore_webdev)


@task
def deploy_core(ctx, name, tests=False, suffix=None, usergroup=None):
    """deploy/update lambdas only"""
    _deploy_core(name=name, tests=tests, suffix=suffix, usergroup=usergroup)


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
    _setup_tibanna_env(buckets=buckets, usergroup_tag=usergroup_tag, no_randomize=no_randomize, verbose=verbose)


@task
def deploy_tibanna(ctx, suffix=None, sfn_type='pony', usergroup=None, tests=False,
                   setup=False, buckets='', setenv=False):
    """deploy tibanna unicorn or pony to AWS cloud (pony is for 4DN-DCIC only)"""
    _deploy_tibanna(suffix=suffix, sfn_type=sfn_type, usergroup=usergroup, tests=tests)


@task
def deploy_unicorn(ctx, suffix=None, no_setup=False, buckets='',
                   no_setenv=False, usergroup=None):
    """deploy tibanna unicorn to AWS cloud"""
    _deploy_unicorn(suffix=suffix, no_setup=no_setup, buckets=buckets, no_setenv=no_setenv,
                    usergroup=usergroup)


@task
def add_user(ctx, user, usergroup):
    """add a user to a tibanna group"""
    _add_user(user=user, usergroup=usergroup)


@task
def users(ctx):
    """list all users along with their associated tibanna user groups"""
    _users()


@task
def list(ctx, numbers=False, sfn_type="unicorn"):
    """list all step functions, optionally with a summary (-n)"""
    _list_sfns(numbers=False, sfn_type="unicorn")


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
    _stat(sfn=sfn, status=status, verbose=verbose)
