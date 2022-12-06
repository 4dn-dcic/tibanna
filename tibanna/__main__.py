"""
CLI for tibanna package
"""

# -*- coding: utf-8 -*-
import argparse
import inspect
import json
from ._version import __version__
# from botocore.errorfactory import ExecutionAlreadyExists
from .core import API
from .vars import (
    TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
    S3_ENCRYT_KEY_ID
)

PACKAGE_NAME = 'tibanna'


class Subcommands(object):

    def __init__(self):
        pass

    @property
    def descriptions(self):
        return {
            # add more later
            'add_user': 'add an (IAM) user to a Tibanna usergroup',
            'deploy_core': 'New method of deploying packaged lambdas (BETA)',
            'deploy_unicorn': 'deploy tibanna unicorn to AWS cloud (unicorn is for everyone)',
            'kill': 'kill a specific job',
            'kill_all': 'kill all the running jobs on a step function',
            'list_sfns': 'list all step functions, optionally with a summary (-n)',
            'log': 'print execution log or postrun json for a job',
            'info': 'print out information about a job',
            'rerun': 'rerun a specific job',
            'rerun_many': 'rerun all the jobs that failed after a given time point',
            'run_workflow': 'run a workflow',
            'run_batch_workflows': 'run many workflows in a batch',
            'setup_tibanna_env': 'set up usergroup environment on AWS.' +
                                 'This function is called automatically by deploy_tibanna or deploy_unicorn.' +
                                 'Use it only when the IAM permissions need to be reset',
            'stat': 'print out executions with details',
            'users': 'list all users along with their associated tibanna user groups',
            'plot_metrics': 'create a metrics report html and upload it to S3, or retrieve one if one already exists',
            'cost': 'print out the EC2/EBS cost of a job - it may not be ready for a day after a job finishes',
            'cost_estimate': 'print out the EC2/EBS estimated cost of a job - available as soon as the job finished. Returns the exact costs, if available',
            'cleanup': 'remove all tibanna component for a usergroup (and suffix) including step function, lambdas IAM groups',
            'create_ami': 'create tibanna ami (Most users do not need this - tibanna AMIs are publicly available.)'
        }

    @property
    def args(self):
        return {
            'run_workflow':
                [{'flag': ["-i", "--input-json"], 'help': "tibanna input json file"},
                 {'flag': ["-s", "--sfn"],
                  'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                          "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                  'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
                 {'flag': ["-j", "--jobid"],
                  'help': "specify a user-defined job id (randomly generated if not specified)"},
                 {'flag': ["-B", "--do-not-open-browser"],
                  'help': "Do not open browser",
                  'action': "store_true"},
                 {'flag': ["-S", "--sleep"],
                  'help': "number of seconds between submission, to avoid drop-out (default 3)",
                  'type': int,
                  'default': 3}],
            'run_batch_workflows':
                [{'flag': ["-i", "--input-json-list"],
                  'help': "list of tibanna input json files, e.g. -i input1.json [input2.json] [...]",
                  "nargs": "+"},
                 {'flag': ["-s", "--sfn"],
                  'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                          "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                  'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
                 {'flag': ["-S", "--sleep"],
                  'help': "number of seconds between submission, to avoid drop-out (default 3)",
                  'type': int,
                  'default': 3}],
            'stat':
                [{'flag': ["-s", "--sfn"],
                  'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                          "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
                 {'flag': ["-t", "--status"],
                  'help': "filter by status; 'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'"},
                 {'flag': ["-l", "--long"],
                  'help': "more comprehensive information",
                  'action': "store_true"},
                 {'flag': ["-n", "--nlines"],
                  'help': "number of lines to print",
                  'type': int},
                 {'flag': ["-j", "--job-ids"],
                  'nargs': '+',
                  'help': "job ids of the specific jobs to display, separated by space. " +
                          "This option cannot be combined with --nlines(-n), --status(-t) or --sfn(-s)"}],
            'kill':
                [{'flag': ["-e", "--exec-arn"],
                  'help': "execution arn of the specific job to kill"},
                 {'flag': ["-j", "--job-id"],
                  'help': "job id of the specific job to kill (alternative to --exec-arn/-e)"},
                 {'flag': ["-s", "--sfn"],
                  'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                          "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                  'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
                 {'flag': ["-z", "--soft"],
                  'help': "instead of directly killing the execution, " +
                          "send abort signal to s3 so that step function can handle it",
                  'action': "store_true"}],
            'kill_all':
                [{'flag': ["-s", "--sfn"],
                  'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                          "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                  'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
                 {'flag': ["-z", "--soft"],
                  'help': "instead of directly killing the execution, " +
                          "send abort signal to s3 so that step function can handle it",
                  'action': "store_true"}],
            'log':
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
                 {'flag': ["-r", "--runjson"],
                  'help': "print out run json instead", 'action': "store_true"},
                 {'flag': ["-p", "--postrunjson"],
                  'help': "print out postrun json instead", 'action': "store_true"},
                 {'flag': ["-t", "--top"],
                  'help': "print out top file (log file containing top command output) instead", 'action': "store_true"},
                 {'flag': ["-T", "--top-latest"],
                  'help': "print out the latest content of the top file", 'action': "store_true"}],
            'info':
                [{'flag': ["-j", "--job-id"],
                  'help': "job id of the specific job to log (alternative to --exec-arn/-e)"}],
            'add_user':
                [{'flag': ["-u", "--user"],
                  'help': "user to add to a Tibanna usergroup"},
                 {'flag': ["-g", "--usergroup"],
                  'help': "Tibanna usergroup to add the user to"}],
            'list_sfns':
                [{'flag': ["-s", "--sfn-type"],
                  'default': 'unicorn',
                  'help': "tibanna step function type ('unicorn' vs 'pony')"},
                 {'flag': ["-n", "--numbers"],
                  'help': "print out the number of executions along with the step functions",
                  'action': "store_true"}],
            'rerun':
                [{'flag': ["-e", "--exec-arn"],
                  'help': "execution arn of the specific job to rerun"},
                 {'flag': ["-j", "--job-id"],
                  'help': "job id of the specific job to rerun (alternative to --exec-arn/-e)"},
                 {'flag': ["-s", "--sfn"],
                  'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                  'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                          "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
                 {'flag': ["-a", "--app-name-filter"],
                  'help': "rerun only the ones that match this appname"},
                 {'flag': ["-i", "--instance-type"],
                  'help': "use a specified instance type for the rerun"},
                 {'flag': ["-d", "--shutdown-min"],
                  'help': "use a specified shutdown mininutes for the rerun"},
                 {'flag': ["-b", "--ebs-size"],
                  'help': "use a specified ebs size for the rerun (GB)"},
                 {'flag': ["-T", "--ebs-type"],
                  'help': "use a specified ebs type for the rerun (gp2 vs io1)"},
                 {'flag': ["-p", "--ebs-iops"],
                  'help': "use a specified ebs iops for the rerun"},
                 {'flag': ["-w", "--ebs-throughput"],
                  'help': "use a specified ebs throughput (for gp3 type EBS) for the rerun"},
                 {'flag': ["-k", "--key-name"],
                  'help': "use a specified key name for the rerun"},
                 {'flag': ["-n", "--name"],
                  'help': "use a specified run name for the rerun"},
                 {'flag': ["-u", "--use-spot"],
                  'help': "use spot instance for the rerun",
                  'action': "store_true"},
                 {'flag': ["-U", "--do-not-use-spot"],
                  'help': "do not use spot instance for the rerun",
                  'action': "store_true"},
                 {'flag': ["-x", "--overwrite-input-extra"],
                  'help': "overwrite input extra file if it already exists (reserved for pony)"}],
            'rerun_many':
                [{'flag': ["-s", "--sfn"],
                  'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                  'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                          "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
                 {'flag': ["-D", "--stopdate"],
                  'default': '13Feb2018',
                  'help': "stop (end) date of the executions (e.g. '13Feb2018')"},
                 {'flag': ["-H", "--stophour"],
                  'type': int,
                  'default': 13,
                  'help': "stop (end) hour of the executions (e.g. 13, for 1pm)"},
                 {'flag': ["-M", "--stopminute"],
                  'type': int,
                  'default': 0,
                  'help': "stop (end) minute of the executions (e.g. 55)"},
                 {'flag': ["-o", "--offset"],
                  'default': 0,
                  'help': "offset for time zone between local computer and AWS step function"},
                 {'flag': ["-r", "--sleeptime"],
                  'type': int,
                  'default': 5,
                  'help': "minutes to sleep between runs to avoid drop outs"},
                 {'flag': ["-t", "--status"],
                  'default': 'FAILED',
                  'help': "filter by status (e.g. if set to FAILED, rerun only FAILED jobs); " +
                          "'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'"},
                 {'flag': ["-a", "--app-name-filter"],
                  'help': "rerun only the ones that match this appname"},
                 {'flag': ["-i", "--instance-type"],
                  'help': "use a specified instance type for the rerun"},
                 {'flag': ["-d", "--shutdown-min"],
                  'help': "use a specified shutdown mininutes for the rerun"},
                 {'flag': ["-b", "--ebs-size"],
                  'help': "use a specified ebs size for the rerun (GB)"},
                 {'flag': ["-T", "--ebs-type"],
                  'help': "use a specified ebs type for the rerun (gp2 vs io1)"},
                 {'flag': ["-p", "--ebs-iops"],
                  'help': "use a specified ebs iops for the rerun"},
                 {'flag': ["-w", "--ebs-throughput"],
                  'help': "use a specified ebs throughput (for gp3 type EBS) for the rerun"},
                 {'flag': ["-k", "--key-name"],
                  'help': "use a specified key name for the rerun"},
                 {'flag': ["-n", "--name"],
                  'help': "use a specified run name for the rerun"},
                 {'flag': ["-u", "--use-spot"],
                  'help': "use spot instance for the rerun",
                  'action': "store_true"},
                 {'flag': ["-U", "--do-not-use-spot"],
                  'help': "do not use spot instance for the rerun",
                  'action': "store_true"},
                 {'flag': ["-x", "--overwrite-input-extra"],
                  'help': "overwrite input extra file if it already exists (reserved for pony)"}],
            'setup_tibanna_env':
                [{'flag': ["-b", "--buckets"],
                  'help': "list of buckets to add permission to a tibanna usergroup"},
                 {'flag': ["-g", "--usergroup-tag"],
                  'help': "tibanna usergroup tag you want to use " +
                          "(e.g. name of a specific tibanna usergroup"},
                 {'flag': ["-R", "--no-randomize"],
                  'help': "do not add random numbers to the usergroup tag to generate usergroup name",
                  'action': "store_true"},
                 {'flag': ["-P", "--do-not-delete-public-access-block"],
                  'action': "store_true",
                  'help': "Do not delete public access block from buckets" +
                          "(this way postrunjson and metrics reports will not be public)"}],
            'deploy_unicorn':
                [{'flag': ["-s", "--suffix"],
                  'help': "suffix (e.g. 'dev') to add to the end of the name of" +
                          "tibanna_unicorn and AWS Lambda functions within the same usergroup"},
                 {'flag': ["-b", "--buckets"],
                  'help': "list of buckets to add permission to a tibanna usergroup"},
                 {'flag': ["-S", "--no-setup"],
                  'help': "do not perform permission setup; just update step functions / lambdas",
                  'action': "store_true"},
                {'flag': ["-C", "--deploy-costupdater"],
                  'help': "deploy the cost updater step function",
                  'action': "store_true"},
                 {'flag': ["-E", "--no-setenv"],
                  'help': "Do not overwrite TIBANNA_DEFAULT_STEP_FUNCTION_NAME" +
                          "environmental variable in your .bashrc",
                  'action': "store_true"},
                 {'flag': ["-g", "--usergroup"],
                  'default': '',
                  'help': "Tibanna usergroup to share the permission to access buckets and run jobs"},
                 {'flag': ["-P", "--do-not-delete-public-access-block"],
                  'action': "store_true",
                  'help': "Do not delete public access block from buckets" +
                          "(this way postrunjson and metrics reports will not be public)"},
                 {'flag': ["-t", "--subnets"],
                  'nargs': '+',
                  'help': "subnet IDs"},
                 {'flag': ["-r", "--security-groups"],
                  'nargs': '+',
                  'help': "security groups"},
                 {'flag': ["-q", "--quiet"],
                  'action': "store_true",
                  'help': "minimize standard output from deployment"}],
            'deploy_core':
                [{'flag': ["-n", "--name"],
                  'help': "name of the lambda function to deploy (e.g. run_task_awsem)"},
                 {'flag': ["-s", "--suffix"],
                  'help': "suffix (e.g. 'dev') to add to the end of the name of the AWS " +
                          "Lambda function, within the same usergroup"},
                 {'flag': ["-g", "--usergroup"],
                  'default': '',
                  'help': "Tibanna usergroup for the AWS Lambda function"},
                 {'flag': ["-t", "--subnets"],
                  'nargs': '+',
                  'help': "subnet IDs"},
                 {'flag': ["-r", "--security-groups"],
                  'nargs': '+',
                  'help': "security groups"},
                 {'flag': ["-q", "--quiet"],
                  'action': "store_true",
                  'help': "minimize standard output from deployment"}],
            'plot_metrics':
                [{'flag': ["-j", "--job-id"],
                  'help': "job id of the specific job to log (alternative to --exec-arn/-e)"},
                 {'flag': ["-s", "--sfn"],
                  'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                          "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                  'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
                 {'flag': ["-f", "--force-upload"],
                  'help': "upload the metrics report to s3 bucket even if there is a lock",
                  'action': "store_true"},
                 {'flag': ["-B", "--do-not-open-browser"],
                  'help': "Do not open browser",
                  'action': "store_true"},
                 {'flag': ["-u", "--update-html-only"],
                  'help': "update html only and do not update the text files",
                  'action': "store_true"},
                 {'flag': ["-e", "--endtime"],
                  'help': "endtime (default job end time if the job has finished or the current time)"},
                 {'flag': ["-i", "--instance_id"],
                  'help': "manually provide instance_id if somehow tibanna fails to retrieve the info"}],
            'cost':
                [{'flag': ["-j", "--job-id"],
                  'help': "job id of the specific job to log (alternative to --exec-arn/-e)"},
                 {'flag': ["-s", "--sfn"],
                  'help': "tibanna step function name (e.g. 'tibanna_unicorn_monty'); " +
                          "your current default is %s)" % TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
                  'default': TIBANNA_DEFAULT_STEP_FUNCTION_NAME},
                 {'flag': ["-u", "--update-tsv"],
                  'help': "add cost to the metric tsv file on S3",
                  'action': "store_true"}],
            'cost_estimate':
                [{'flag': ["-j", "--job-id"],
                  'help': "job id of the specific job to log (alternative to --exec-arn/-e)"},
                 {'flag': ["-u", "--update-tsv"],
                  'help': "update estimated cost in the metric tsv file on S3",
                  'action': "store_true"},
                  {'flag': ["-f", "--force"],
                  'action': "store_true",
                  'help': "returns the estimate, even if the actual cost is available"}],
            'cleanup':
                [{'flag': ["-g", "--usergroup"],
                  'help': "Tibanna usergroup that shares the permission to access buckets and run jobs"},
                 {'flag': ["-s", "--suffix"],
                  'default': '',
                  'help': "suffix (e.g. 'dev') that is added to the end of the name of the AWS " +
                          "Lambda function, within the same usergroup"},
                 {'flag': ["-p", "--purge-history"],
                  'action': 'store_true',
                  'help': "Purge all the logs from S3 and delete all records and history of runs from dynamoDB. If you use this option, you cannot check the logs or other information in the future."},
                 {'flag': ["-G", "--do-not-remove-iam-group"],
                  'action': 'store_true',
                  'help': "Do not remove IAM groups and permission, just remove step functions and lambda"},
                 {'flag': ["-q", "--quiet"],
                  'action': 'store_true',
                  'help': "quiet"},
                 {'flag': ["-E", "--do-not-ignore-errors"],
                  'action': 'store_true',
                  'help': "do not ignore errors that occur due to a resource already deleted or non-existent"}],
            'create_ami':
                [{'flag': ["-p", "--make-public"],
                  'help': "Make the Tibanna AMI public (most users do not need this)",
                  'action': 'store_true'},
                 {'flag': ["-B", "--build-from-scratch"],
                  'help': "Build a new AMI starting from Ubuntu base image. " +
                          "This option will launch an instance for creating the new image " +
                          "as opposed to simply copying an existing Tibanna image.",
                  'action': 'store_true'},
                 {'flag': ["-I", "--source-image-to-copy-from"],
                  'help': "The ID of the image to copy (e.g. 'ami-0a7ddfc7e412ab6e0' which is a default public Tibanna image " +
                          "for us-east-1). To use this option, turn off option -B."},
                 {'flag': ["-R", "--source-image-region"],
                  'help': "The region of the image to copy (e.g. 'us-east-1' if source image to copy from is 'ami-0a7ddfc7e412ab6e0'). " +
                          "To use this option, turn off option -B."},
                 {'flag': ["-U", "--ubuntu-base-image"],
                  'help': "The ID of the Ubuntu 20.04 image to build from (e.g. 'ami-0885b1f6bd170450c' for us-east-1). " +
                          "To use this option, turn on the option -B."},
                 {'flag': ["-r", "--replicate"],
                  'help': "Enable to replicate across all regions defined by AMI_PER_REGION"},
                  {'flag': ["-a", "--architecture"],
                  'help': "Architecture: x86 or Arm. Default: x86. " +
                          "To use this option, turn on option -B. Ignored when option -U is used.",
                  'default': "x86"}
                 ]
        }


def deploy_core(name, suffix=None, usergroup='', quiet=False, subnets=None, security_groups=None):
    """
    New method of deploying packaged lambdas (BETA)
    """
    API().deploy_core(name=name, suffix=suffix, usergroup=usergroup, subnets=subnets,
                      security_groups=security_groups, quiet=quiet)


def run_workflow(input_json, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, jobid='', do_not_open_browser=False, sleep=3):
    """run a workflow"""
    API().run_workflow(input_json, sfn=sfn, jobid=jobid, sleep=sleep, open_browser=not do_not_open_browser, verbose=True)


def run_batch_workflows(input_json_list, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, sleep=3):
    """run a workflow"""
    API().run_batch_workflows(input_json_list, sfn=sfn, sleep=sleep, verbose=True)


def setup_tibanna_env(buckets='', usergroup_tag='default', no_randomize=False,
                      do_not_delete_public_access_block=False):
    """set up usergroup environment on AWS
    This function is called automatically by deploy_tibanna or deploy_unicorn
    Use it only when the IAM permissions need to be reset"""
    API().setup_tibanna_env(buckets=buckets, usergroup_tag=usergroup_tag, no_randomize=no_randomize,
                            do_not_delete_public_access_block=do_not_delete_public_access_block, verbose=False)


def deploy_unicorn(suffix=None, no_setup=False, buckets='',
                   no_setenv=False, usergroup='', do_not_delete_public_access_block=False,
                   deploy_costupdater=False, subnets=None, security_groups=None, quiet=False):
    """deploy tibanna unicorn to AWS cloud"""
    API().deploy_unicorn(suffix=suffix, no_setup=no_setup, buckets=buckets, no_setenv=no_setenv,
                         usergroup=usergroup, do_not_delete_public_access_block=do_not_delete_public_access_block,
                         deploy_costupdater=deploy_costupdater, subnets=subnets, security_groups=security_groups,
                         quiet=quiet)


def add_user(user, usergroup):
    """add a user to a tibanna group"""
    API().add_user(user=user, usergroup=usergroup)


def users():
    """list all users along with their associated tibanna user groups"""
    API().users()


def list_sfns(numbers=False):
    """list all step functions, optionally with a summary (-n)"""
    API().list_sfns(numbers=numbers)


def log(exec_arn=None, job_id=None, exec_name=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
        runjson=False, postrunjson=False, top=False, top_latest=False):
    """print execution log, run json (-r), postrun json (-p) or top (-t) for a job"""
    print(API().log(exec_arn, job_id, exec_name, sfn, runjson=runjson, postrunjson=postrunjson,
                    top=top, top_latest=top_latest))


def kill_all(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, soft=False):
    """kill all the running jobs on a step function"""
    API().kill_all(sfn, soft=soft)


def kill(exec_arn=None, job_id=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, soft=False):
    """kill a specific job"""
    API().kill(exec_arn, job_id, sfn, soft=soft)


def info(job_id):
    """prints out information about a job"""
    print(json.dumps(API().info(job_id), indent=True))


def rerun(exec_arn=None, job_id=None, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, app_name_filter=None,
          instance_type=None, shutdown_min=None, ebs_size=None, ebs_type=None, ebs_iops=None, ebs_throughput=None,
          overwrite_input_extra=None, key_name=None, name=None, use_spot=None, do_not_use_spot=None):
    """ rerun a specific job"""
    API().rerun(exec_arn=exec_arn, job_id=job_id, sfn=sfn,
                app_name_filter=app_name_filter, instance_type=instance_type, shutdown_min=shutdown_min,
                ebs_size=ebs_size, ebs_type=ebs_type, ebs_iops=ebs_iops, ebs_throughput=ebs_throughput,
                overwrite_input_extra=overwrite_input_extra, key_name=key_name, name=name,
                use_spot=use_spot, do_not_use_spot=do_not_use_spot)


def rerun_many(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, stopdate='13Feb2018', stophour=13,
               stopminute=0, offset=0, sleeptime=5, status='FAILED', app_name_filter=None,
               instance_type=None, shutdown_min=None, ebs_size=None, ebs_type=None, ebs_iops=None, ebs_throughput=None,
               overwrite_input_extra=None, key_name=None, name=None, use_spot=None, do_not_use_spot=None):
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
                     app_name_filter=app_name_filter, instance_type=instance_type, shutdown_min=shutdown_min,
                     ebs_size=ebs_size, ebs_type=ebs_type, ebs_iops=ebs_iops, ebs_throughput=ebs_throughput,
                     overwrite_input_extra=overwrite_input_extra, key_name=key_name, name=name,
                     use_spot=use_spot, do_not_use_spot=do_not_use_spot)


def stat(sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, status=None, long=False, nlines=None, job_ids=None):
    """print out executions with details
    status can be one of 'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'
    """
    API().stat(sfn=sfn, status=status, verbose=long, n=nlines, job_ids=job_ids)


def plot_metrics(job_id, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, force_upload=False, update_html_only=False,
                 endtime='', do_not_open_browser=False, instance_id=''):
    """create a resource metrics report html"""
    API().plot_metrics(job_id=job_id, sfn=sfn, force_upload=force_upload, update_html_only=update_html_only,
                       endtime=endtime, open_browser=not do_not_open_browser, instance_id=instance_id)


def cost(job_id, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, update_tsv=False):
    """print out cost of a specific job"""
    print(API().cost(job_id=job_id, sfn=sfn, update_tsv=update_tsv))

def cost_estimate(job_id, update_tsv=False, force=False):
    """print out estimated cost of a specific job"""
    cost_estimate, cost_estimate_type = API().cost_estimate(job_id=job_id, update_tsv=update_tsv, force=force)
    print(f'{cost_estimate} ({cost_estimate_type})')


def cleanup(usergroup, suffix='', purge_history=False, do_not_remove_iam_group=False, do_not_ignore_errors=False, quiet=False):
    API().cleanup(user_group_name=usergroup, suffix=suffix, do_not_remove_iam_group=do_not_remove_iam_group,
                  ignore_errors=not do_not_ignore_errors, purge_history=purge_history, verbose=not quiet)


def create_ami(make_public=False, build_from_scratch=False, source_image_to_copy_from=None, source_image_region=None,
               ubuntu_base_image=None, replicate=False, architecture="x86"):
    print(API().create_ami(make_public=make_public, build_from_scratch=build_from_scratch,
                           source_image_to_copy_from=source_image_to_copy_from, source_image_region=source_image_region,
                           ubuntu_base_image=ubuntu_base_image, replicate=replicate, architecture=architecture))


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
