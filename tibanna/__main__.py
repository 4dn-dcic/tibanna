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


subcommand_desc = {
    # add more later
    'add_user': 'add an (IAM) user to a Tibanna usergroup',
    'kill': 'kill a specific job',
    'kill_all': 'kill all the running jobs on a step function',
    'log': 'print execution log or postrun json for a job',
    'run_workflow': 'run a workflow',
    'stat': 'print out executions with details',
    'users': 'list all users along with their associated tibanna user groups',
}


def main():
    """
    Execute the program from the command line
    """
    # raise NotImplementedError
    # the primary parser is used for tibanna -v or -h
    primary_parser = argparse.ArgumentParser(prog='tibanna', add_help=False)
    primary_parser.add_argument('-v', '--version', action='version',
                                version='%(prog)s ' + __version__)
    # the secondary parser is used for the specific run mode
    secondary_parser = argparse.ArgumentParser(prog='tibanna', parents=[primary_parser])
    # the subparsers collect the args used to run the hic2cool mode
    subparsers = secondary_parser.add_subparsers(
        title='Tibanna subcommands',
        description='choose one of the following subcommands to run tibanna:',
        dest='subcommand',
        metavar='subcommand: {%s}' % ', '.join(subcommand_desc.keys())
    )
    subparsers.required = True

    subparser = dict()
    for sc, desc in subcommand_desc.items():
        subparser[sc] = subparsers.add_parser(sc, help=desc, description=desc)

    subparser['run_workflow'].add_argument("-i", "--input-json",
                                           help="tibanna input json file")
    subparser['run_workflow'].add_argument("-s", "--sfn", default=TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                                           help="tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                                                "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME)
    subparser['run_workflow'].add_argument("-j", "--jobid",
                                           help="specify a user-defined job id (randomly generated if not specified)")

    subparser['stat'].add_argument("-s", "--sfn", default=TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                                   help="tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                                        "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME)
    subparser['stat'].add_argument("-t", "--status",
                                   help="filter by status; 'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'")
    subparser['stat'].add_argument("-l", "--long",
                                   help="more comprehensive information", action="store_true")

    subparser['kill'].add_argument("-e", "--exec-arn",
                                   help="execution arn of the specific job to kill")
    subparser['kill'].add_argument("-j", "--job-id",
                                   help="job id of the specific job to kill (alternative to --exec-arn/-e)")
    subparser['kill'].add_argument("-s", "--sfn", default=TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                                   help="tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                                        "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME)

    subparser['kill_all'].add_argument("-s", "--sfn", default=TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                                       help="tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                                            "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME)

    subparser['log'].add_argument("-e", "--exec-arn",
                                  help="execution arn of the specific job to log")
    subparser['log'].add_argument("-j", "--job-id",
                                  help="job id of the specific job to log (alternative to --exec-arn/-e)")
    subparser['log'].add_argument("-n", "--exec-name",
                                  help="execution name of the specific job to log " +
                                       "(alternative to --exec-arn/-e or --job-id/-j")
    subparser['log'].add_argument("-s", "--sfn", default=TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                                  help="tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                                       "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME)
    subparser['log'].add_argument("-p", "--postrunjson",
                                  help="print out postrun json instead", action="store_true")

    subparser['add_user'].add_argument("-u", "--user",
                                       help="user to add to a Tibanna usergroup")
    subparser['add_user'].add_argument("-g", "--usergroup",
                                       help="Tibanna usergroup to add the user to")


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


def setup_tibanna_env(buckets='', usergroup_tag='default', no_randomize=False, verbose=False):
    """set up usergroup environment on AWS
    This function is called automatically by deploy_tibanna or deploy_unicorn
    Use it only when the IAM permissions need to be reset"""
    _setup_tibanna_env(buckets=buckets, usergroup_tag=usergroup_tag, no_randomize=no_randomize, verbose=verbose)


def deploy_tibanna(suffix=None, sfn_type='pony', usergroup=None, tests=False,
                   setup=False, buckets='', setenv=False):
    """deploy tibanna unicorn or pony to AWS cloud (pony is for 4DN-DCIC only)"""
    _deploy_tibanna(suffix=suffix, sfn_type=sfn_type, usergroup=usergroup, tests=tests)


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


def list(numbers=False, sfn_type="unicorn"):
    """list all step functions, optionally with a summary (-n)"""
    _list_sfns(numbers=False, sfn_type="unicorn")


def rerun(exec_arn, sfn='tibanna_pony',
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
