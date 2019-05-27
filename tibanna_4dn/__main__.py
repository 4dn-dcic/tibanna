"""
CLI for tibanna_4dn package
"""

# -*- coding: utf-8 -*-
import argparse
import inspect
from tibanna._version import __version__  # for now use the same version as tibanna
# from botocore.errorfactory import ExecutionAlreadyExists
from .vars import (
    TIBANNA_DEFAULT_STEP_FUNCTION_NAME
)
# do not delete imported but unused functions below.
from .core import API
from tibanna.test_utils import test as _test
from tibanna.__main__ import Subcommands as _Subcommands

PACKAGE_NAME = 'tibanna_4dn'


class Subcommands(_Subcommands):

    default_sfn = TIBANNA_DEFAULT_STEP_FUNCTION_NAME

    def __init__(self):
        pass

    @property
    def descriptions(self):
        desc = super().descriptions
        desc['deploy_pony'] = 'deploy tibanna pony to AWS cloud (pony is for 4DN-DCIC only)'
        return desc

    @property
    def args(self):
        _args = super().args
        _args['deploy_pony'] = \
            [{'flag': ["-s", "--suffix"],
              'help': "suffix (e.g. 'dev') to add to the end of the name of" +
                      "tibanna_pony and AWS Lambda functions within the same usergroup"},
             {'flag': ["-t", "--tests"],
              'help': "Perform tests", 'action': "store_true"}]
        return _args


def test(watch=False, last_failing=False, no_flake=False, k='',  extra='',
         ignore='', ignore_pony=False, ignore_webdev=False):
    """Run the tests.
    Note: --watch requires pytest-xdist to be installed.
    """
    _test(watch=watch, last_failing=last_failing, no_flake=no_flake, k=k,
          extra=extra, ignore=ignore, ignore_pony=ignore_pony, ignore_webdev=ignore_webdev)


def deploy_new(name, tests=True, suffix=None, dev=False, usergroup=None):
    """
    New method of deploying pacaked lambdas (BETA)
    * Running with --dev will cause the Python pkg in the current working dir to be installed
    """
    API().deploy_new(name=name, tests=tests, suffix=suffix, dev=dev, usergroup=usergroup)


def deploy_pony(suffix=None, tests=True):
    """deploy tibanna unicorn or pony to AWS cloud (pony is for 4DN-DCIC only)"""
    API().deploy_pony(suffix=suffix, tests=tests)


def run_workflow(input_json, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, jobid='', sleep=3):
    API().run_workflow(input_json=input_json, sfn=sfn, jobid=jobid, sleep=sleep, verbose=True)


def list_sfns(numbers=False):
    """list all step functions, optionally with a summary (-n)"""
    API().list_sfns(numbers=numbers)


def log(exec_arn=None, job_id=None, exec_name=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, postrunjson=False):
    API().log(exec_arn, job_id, exec_name, sfn, postrunjson)


def kill_all(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    """kill all the running jobs on a step function"""
    API().kill_all(sfn)


def kill(exec_arn=None, job_id=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
    """kill a specific job"""
    API().kill(exec_arn, job_id, sfn)


def rerun(exec_arn, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, appname_filter=None,
          instance_type=None, shutdown_min=None, ebs_size=None, ebs_type=None, ebs_iops=None,
          overwrite_input_extra=None, key_name=None, name=None):
    """ rerun a specific job"""
    API().rerun(exec_arn, sfn=sfn,
                appname_filter=appname_filter, instance_type=instance_type, shutdown_min=shutdown_min,
                ebs_size=ebs_size, ebs_type=ebs_type, ebs_iops=ebs_iops,
                overwrite_input_extra=overwrite_input_extra, key_name=key_name, name=name)


def rerun_many(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, stopdate='13Feb2018', stophour=13,
               stopminute=0, offset=0, sleeptime=5, status='FAILED', appname_filter=None,
               instance_type=None, shutdown_min=None, ebs_size=None, ebs_type=None, ebs_iops=None,
               overwrite_input_extra=None, key_name=None, name=None):
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
    API().rerun_many(sfn=sfn, stopdate=stopdate, stophour=stophour,
                     stopminute=stopminute, offset=offset, sleeptime=sleeptime, status=status,
                     appname_filter=appname_filter, instance_type=instance_type, shutdown_min=shutdown_min,
                     ebs_size=ebs_size, ebs_type=ebs_type, ebs_iops=ebs_iops,
                     overwrite_input_extra=overwrite_input_extra, key_name=key_name, name=name)


def stat(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, status=None, long=False):
    """print out executions with details
    status can be one of 'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'
    """
    API().stat(sfn=sfn, status=status, long=long)


def main(Subcommands=Subcommands):
    """
    Execute the program from the command line
    """
    scs = Subcommands()

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
        metavar='subcommand: {%s}' % ', '.join(scs.descriptions.keys())
    )
    subparsers.required = True

    def add_arg(name, flag, **kwargs):
        subparser[name].add_argument(flag[0], flag[1], **kwargs)

    def add_args(name, argdictlist):
        for argdict in argdictlist:
            add_arg(name, **argdict)

    subparser = dict()
    for sc, desc in scs.descriptions.items():
        subparser[sc] = subparsers.add_parser(sc, help=desc, description=desc)
        if sc in scs.args:
            add_args(sc, scs.args[sc])

    # two step argument parsing
    # first check for top level -v or -h (i.e. `tibanna -v`)
    (primary_namespace, remaining) = primary_parser.parse_known_args()
    # get subcommand-specific args
    args = secondary_parser.parse_args(args=remaining, namespace=primary_namespace)
    subcommandf = eval(args.subcommand)
    sc_args = [getattr(args, sc_arg) for sc_arg in inspect.getargspec(subcommandf).args]
    # run subcommand
    subcommandf(*sc_args)


if __name__ == '__main__':
    main()
