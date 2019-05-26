"""
CLI for tibanna package
"""

# -*- coding: utf-8 -*-
import argparse
import inspect
from ._version import __version__
import shutil
import json
from invoke import run
# from botocore.errorfactory import ExecutionAlreadyExists
from .utils import create_jobid
from .vars import (
    _tibanna,
    AWS_REGION,
    TIBANNA_DEFAULT_STEP_FUNCTION_NAME
)
from .core import (
    run_workflow as _run_workflow,
    kill as _kill,
    log as _log,
    kill_all as _kill_all,
    list_sfns as _list_sfns,
    stat as _stat,
    rerun as _rerun,
    rerun_many as _rerun_many,
    deploy_core as _deploy_core,
    deploy_unicorn as _deploy_unicorn,
    deploy_tibanna as _deploy_tibanna,
    deploy_packaged_lambdas as _deploy_packaged_lambdas,
    users as _users,
    add_user as _add_user,
    setup_tibanna_env as _setup_tibanna_env
)
from .test_utils import test as _test

PACKAGE_NAME = 'tibanna'

subcommand_desc = {
    # add more later
    'add_user': 'add an (IAM) user to a Tibanna usergroup',
    'deploy_core': 'deploy/update lambdas only',
    'deploy_new': 'New method of deploying pacaked lambdas (BETA)',
    'deploy_pony': 'deploy tibanna pony to AWS cloud (pony is for 4DN-DCIC only)',
    'deploy_unicorn': 'deploy tibanna unicorn to AWS cloud (unicorn is for everyone)',
    'kill': 'kill a specific job',
    'kill_all': 'kill all the running jobs on a step function',
    'list_sfns': 'list all step functions, optionally with a summary (-n)',
    'log': 'print execution log or postrun json for a job',
    'rerun': 'rerun a specific job',
    'rerun_many': 'rerun all the jobs that failed after a given time point',
    'run_workflow': 'run a workflow',
    'setup_tibanna_env': 'set up usergroup environment on AWS.' +
                         'This function is called automatically by deploy_tibanna or deploy_unicorn.' +
                         'Use it only when the IAM permissions need to be reset',
    'stat': 'print out executions with details',
    'test': 'test tibanna code (currently reserved for development at 4dn-dcic)',  # test doesn't work
    'users': 'list all users along with their associated tibanna user groups',
}


def main():
    """
    Execute the program from the command line
    """
    # raise NotImplementedError
    # the primary parser is used for tibanna -v or -h
    primary_parser = argparse.ArgumentParser(prog=PACKAGE_NAME, add_help=False)
    primary_parser.add_argument('-v', '--version', action='version',
                                version='%(prog)s ' + __version__)
    # the secondary parser is used for the specific run mode
    secondary_parser = argparse.ArgumentParser(prog=PACKAGE_NAME, parents=[primary_parser])
    # the subparsers collect the args used to run the hic2cool mode
    subparsers = secondary_parser.add_subparsers(
        title=PACKAGE_NAME + ' subcommands',
        description='choose one of the following subcommands to run ' + PACKAGE_NAME,
        dest='subcommand',
        metavar='subcommand: {%s}' % ', '.join(subcommand_desc.keys())
    )
    subparsers.required = True

    subparser = dict()
    for sc, desc in subcommand_desc.items():
        subparser[sc] = subparsers.add_parser(sc, help=desc, description=desc)

    def add_arg(name, flag, **kwargs):
        subparser[name].add_argument(flag[0], flag[1], **kwargs)

    def add_args(name, argdictlist):
        for argdict in argdictlist:
            add_arg(name, **argdict)

    add_args('run_workflow',
             [{'flag': ["-i", "--input-json"], 'help': "tibanna input json file"},
              {'flag': ["-s", "--sfn"],
               'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                       "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
               'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
              {'flag': ["-j", "--jobid"],
               'help': "specify a user-defined job id (randomly generated if not specified)"}])

    add_args('stat',
             [{'flag': ["-s", "--sfn"],
               'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                       "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
               'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
              {'flag': ["-t", "--status"],
               'help': "filter by status; 'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'"},
              {'flag': ["-l", "--long"],
               'help': "more comprehensive information",
               'action': "store_true"}])

    add_args('kill',
             [{'flag': ["-e", "--exec-arn"],
               'help': "execution arn of the specific job to kill"},
              {'flag': ["-j", "--job-id"],
               'help': "job id of the specific job to kill (alternative to --exec-arn/-e)"},
              {'flag': ["-s", "--sfn"],
               'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                       "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
               'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME}])

    add_args('kill_all',
             [{'flag': ["-s", "--sfn"],
               'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                       "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
               'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME}])

    add_args('log',
             [{'flag': ["-e", "--exec-arn"],
               'help': "execution arn of the specific job to log"},
              {'flag': ["-j", "--job-id"],
               'help': "job id of the specific job to log (alternative to --exec-arn/-e)"},
              {'flag': ["-n", "--exec-name"],
               'help': "execution name of the specific job to log " +
                       "(alternative to --exec-arn/-e or --job-id/-j"},
              {'flag': ["-s", "--sfn"],
               'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                       "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
               'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
              {'flag': ["-p", "--postrunjson"],
               'help': "print out postrun json instead", 'action': "store_true"}])

    add_args('add_user',
             [{'flag': ["-u", "--user"],
               'help': "user to add to a Tibanna usergroup"},
              {'flag': ["-g", "--usergroup"],
               'help': "Tibanna usergroup to add the user to"}])

    add_args('list_sfns',
             [{'flag': ["-s", "--sfn-type"],
               'default': 'unicorn',
               'help': "tibanna step function type ('unicorn' vs 'pony')"},
              {'flag': ["-n", "--numbers"],
               'help': "print out the number of executions along with the step functions",
               'action': "store_true"}])

    add_args('test',
             [{'flag': ["-F", "--no-flake"],
               'help': "skip flake8 tests", 'action': "store_true"},
              {'flag': ["-P", "--ignore-pony"],
               'help': "skip tests for tibanna pony", 'action': "store_true"},
              {'flag': ["-W", "--ignore-webdev"],
               'help': "skip tests for 4DN test portal webdev", 'action': "store_true"},
              {'flag': ["-w", "--watch"],
               'help': "watch", 'action': "store_true"},  # need more detail
              {'flag': ["-f", "--last-failing"],
               'help': "last failing", 'action': "store_true"},  # need more detail
              {'flag': ["-i", "--ignore"],
               'help': "ignore"},  # need more detail
              {'flag': ["-x", "--extra"],
               'help': "extra"},  # need more detail
              {'flag': ["-k", "--k"],
               'help': "k"}])  # need more detail

    add_args('rerun',
             [{'flag': ["-e", "--exec-arn"],
               'help': "execution arn of the specific job to rerun"},
              {'flag': ["-s", "--sfn"],
               'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
               'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                       "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
              {'flag': ["-i", "--instance-type"],
               'help': "use a specified instance type for the rerun"},
              {'flag': ["-d", "--shutdown-min"],
               'help': "use a specified shutdown mininutes for the rerun"},
              {'flag': ["-b", "--ebs-size"],
               'help': "use a specified ebs size for the rerun (GB)"},
              {'flag': ["-t", "--ebs-type"],
               'help': "use a specified ebs type for the rerun (gp2 vs io1)"},
              {'flag': ["-p", "--ebs-iops"],
               'help': "use a specified ebs iops for the rerun"},
              {'flag': ["-k", "--key-name"],
               'help': "use a specified key name for the rerun"},
              {'flag': ["-n", "--name"],
               'help': "use a specified run name for the rerun"},
              {'flag': ["-x", "--overwrite-input-extra"],
               'help': "overwrite input extra file if it already exists (reserved for pony)"}])

    add_args('rerun_many',
             [{'flag': ["-s", "--sfn"],
               'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
               'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                       "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
              {'flag': ["-D", "--stopdate"],
               'default': '13Feb2018',
               'help': "stop (end) date of the executions (e.g. '13Feb2018')"},
              {'flag': ["-H", "--stophour"],
               'default': 13,
               'help': "stop (end) hour of the executions (e.g. 13, for 1pm)"},
              {'flag': ["-M", "--stopminute"],
               'default': 0,
               'help': "stop (end) minute of the executions (e.g. 55)"},
              {'flag': ["-o", "--offset"],
               'default': 0,
               'help': "offset for time zone between local computer and AWS step function"},
              {'flag': ["-r", "--sleeptime"],
               'default': 5,
               'help': "minutes to sleep between runs to avoid drop outs"},
              {'flag': ["-t", "--status"],
               'default': 'FAILED',
               'help': "filter by status (e.g. if set to FAILED, rerun only FAILED jobs); " +
                       "'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'"}])

    add_args('setup_tibanna_env',
             [{'flag': ["-b", "--buckets"],
               'help': "list of buckets to add permission to a tibanna usergroup"},
              {'flag': ["-g", "--usergroup-tag"],
               'help': "tibanna usergroup tag you want to use " +
                       "(e.g. name of a specific tibanna usergroup"},
              {'flag': ["-R", "--no-randomize"],
               'help': "do not add random numbers to the usergroup tag to generate usergroup name",
               'action': "store_true"}])

    add_args('deploy_pony',
             [{'flag': ["-s", "--suffix"],
               'help': "suffix to add to the end of tibanna_pony"},
              {'flag': ["-t", "--tests"],
               'help': "Perform tests", 'action': "store_true"}])

    add_args('deploy_unicorn',
             [{'flag': ["-s", "--suffix"],
               'help': "suffix (e.g. 'dev') to add to the end of the name of" +
                       "tibanna_unicorn and AWS Lambda functions within the same usergroup"},
              {'flag': ["-b", "--buckets"],
               'help': "list of buckets to add permission to a tibanna usergroup"},
              {'flag': ["-S", "--no-setup"],
               'help': "do not perform permission setup; just update step functions / lambdas",
               'action': "store_true"},
              {'flag': ["-E", "--no-setenv"],
               'help': "Do not overwrite TIBANNA_DEFAULT_STEP_FUNCTION_NAME" +
                       "environmental variable in your .bashrc",
               'action': "store_true"},
              {'flag': ["-g", "--usergroup"],
               'help': "Tibanna usergroup to share the permission to access buckets and run jobs"}])

    add_args('deploy_core',
             [{'flag': ["-n", "--name"],
               'help': "name of the lambda function to deploy (e.g. run_task_awsem)"},
              {'flag': ["-s", "--suffix"],
               'help': "suffix (e.g. 'dev') to add to the end of the name of the AWS " +
                       "Lambda function, within the same usergroup"},
              {'flag': ["-t", "--tests"],
               'help': "Perform tests", 'action': "store_true"},
              {'flag': ["-g", "--usergroup"],
               'help': "Tibanna usergroup for the AWS Lambda function"}])

    add_args('deploy_new',
             [{'flag': ["-n", "--name"],
               'help': "name of the lambda function to deploy (e.g. run_task_awsem)"},
              {'flag': ["-s", "--suffix"],
               'help': "suffix (e.g. 'dev') to add to the end of the name of the AWS " +
                       "Lambda function, within the same usergroup"},
              {'flag': ["-d", "--dev"],
               'help': "This will cause the Python pkg in the current working dir to be installed",
               'action': 'store_true'},
              {'flag': ["-g", "--usergroup"],
               'help': "Tibanna usergroup for the AWS Lambda function"}])

    # two step argument parsing
    # first check for top level -v or -h (i.e. `tibanna -v`)
    (primary_namespace, remaining) = primary_parser.parse_known_args()
    # get subcommand-specific args
    args = secondary_parser.parse_args(args=remaining, namespace=primary_namespace)
    subcommandf = eval(args.subcommand)
    sc_args = [getattr(args, sc_arg) for sc_arg in inspect.getargspec(subcommandf).args]
    # run subcommand
    subcommandf(*sc_args)


def test(watch=False, last_failing=False, no_flake=False, k='',  extra='',
         ignore='', ignore_pony=False, ignore_webdev=False):
    """Run the tests.
    Note: --watch requires pytest-xdist to be installed.
    """
    _test(watch=watch, last_failing=last_failing, no_flake=no_flake, k=k,
          extra=extra, ignore=ignore, ignore_pony=ignore_pony, ignore_webdev=ignore_webdev)


def deploy_new(name, suffix=None, dev=False, usergroup=None):
    """
    New method of deploying pacaked lambdas (BETA)
    * Running with --dev will cause the Python pkg in the current working dir to be installed
    """
    _deploy_packaged_lambdas(name, suffix, dev, usergroup=usergroup)


def deploy_core(name, tests=False, suffix=None, usergroup=None):
    """deploy/update lambdas only"""
    _deploy_core(name=name, tests=tests, suffix=suffix, usergroup=usergroup)


def run_workflow(input_json='', sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, jobid=''):
    """run a workflow"""
    if not jobid:
        jobid = create_jobid()
    with open(input_json) as input_file:
        data = json.load(input_file)
        resp = _run_workflow(data, sfn=sfn, jobid=jobid)
        print("JOBID %s submitted" % resp['jobid'])
        print("EXECUTION ARN = %s" % resp[_tibanna]['exec_arn'])
        if 'cloudwatch_dashboard' in resp['config'] and resp['config']['cloudwatch_dashboard']:
            cw_db_url = 'https://console.aws.amazon.com/cloudwatch/' + \
                'home?region=%s#dashboards:name=awsem-%s' % (AWS_REGION, jobid)
            print("Cloudwatch Dashboard = %s" % cw_db_url)
        if shutil.which('open') is not None:
            run('open %s' % resp[_tibanna]['url'])


def setup_tibanna_env(buckets='', usergroup_tag='default', no_randomize=False):
    """set up usergroup environment on AWS
    This function is called automatically by deploy_tibanna or deploy_unicorn
    Use it only when the IAM permissions need to be reset"""
    _setup_tibanna_env(buckets=buckets, usergroup_tag=usergroup_tag, no_randomize=no_randomize, verbose=False)


def deploy_pony(suffix=None, tests=False):
    """deploy tibanna unicorn or pony to AWS cloud (pony is for 4DN-DCIC only)"""
    _deploy_tibanna(suffix=suffix, sfn_type='pony', tests=tests)


def deploy_unicorn(suffix=None, no_setup=False, buckets='',
                   no_setenv=False, usergroup=None):
    """deploy tibanna unicorn to AWS cloud"""
    _deploy_unicorn(suffix=suffix, no_setup=no_setup, buckets=buckets, no_setenv=no_setenv,
                    usergroup=usergroup)


def add_user(user, usergroup):
    """add a user to a tibanna group"""
    _add_user(user=user, usergroup=usergroup)


def users():
    """list all users along with their associated tibanna user groups"""
    _users()


def list_sfns(numbers=False, sfn_type="unicorn"):
    """list all step functions, optionally with a summary (-n)"""
    _list_sfns(numbers=numbers, sfn_type="unicorn")


def rerun(exec_arn, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
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


def log(exec_arn=None, job_id=None, exec_name=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, postrunjson=False):
    """print execution log or postrun json (-p) for a job"""
    print(_log(exec_arn, job_id, exec_name, sfn, postrunjson))


def kill_all(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    """kill all the running jobs on a step function"""
    _kill_all(sfn)


def kill(exec_arn=None, job_id=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    """kill a specific job"""
    _kill(exec_arn, job_id, sfn)


def rerun_many(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, stopdate='13Feb2018', stophour=13,
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


def stat(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, status=None, long=False):
    """print out executions with details
    status can be one of 'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'
    """
    _stat(sfn=sfn, status=status, verbose=long)


if __name__ == '__main__':
    main()
