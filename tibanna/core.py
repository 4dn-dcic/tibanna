# -*- coding: utf-8 -*-
import os
import boto3
import json
import time
import copy
import logging
import importlib
import shutil
import subprocess
from datetime import datetime
from uuid import uuid4, UUID
from types import ModuleType
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
from .utils import (
    _tibanna_settings,
    printlog,
    create_jobid,
)
from .ec2_utils import (
    upload_workflow_to_s3
)
# from botocore.errorfactory import ExecutionAlreadyExists
from .iam_utils import (
    create_tibanna_iam,
    get_ec2_role_name,
    get_lambda_role_name,
)
from .stepfunction import StepFunctionUnicorn


# logger
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


UNICORN_LAMBDAS = ['run_task_awsem', 'check_task_awsem']


class API(object):

    # This one cannot be imported in advance, because it causes circular import.
    # lambdas run_workflow / validate_md5_s3_initiator needs to import this API
    # to call run_workflow (this is a pony problem but to be consistent, I add
    # lambdas_module here for unicorn as well.
    @property
    def lambdas_module(self):
        from . import lambdas as unicorn_lambdas
        return unicorn_lambdas

    @property
    def lambda_names(self):
        return [mod for mod in dir(self.lambdas_module)
                if isinstance(getattr(self.lambdas_module, mod), ModuleType)]

    @property
    def tibanna_packages(self):
        import tibanna
        return [tibanna]

    StepFunction = StepFunctionUnicorn
    default_stepfunction_name = TIBANNA_DEFAULT_STEP_FUNCTION_NAME
    default_env = ''
    sfn_type = 'unicorn'

    def __init__(self):
        pass

    def randomize_run_name(self, run_name, sfn):
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

    def run_workflow(self, input_json, sfn=None,
                     env=None, jobid=None, sleep=3, verbose=True, open_browser=True):
        '''
        input_json is either a dict or a file
        accession is unique name that we be part of run id
        '''
        if not jobid:
            jobid = create_jobid()
        if isinstance(input_json, dict):
            data = copy.deepcopy(input_json)
        elif isinstance(input_json, str) and os.path.exists(input_json):
            with open(input_json) as input_file:
                data = json.load(input_file)
        else:
            raise Exception("input json must be either a file or a dictionary")
        if not sfn:
            sfn = self.default_stepfunction_name
        if not env:
            env = self.default_env
        client = boto3.client('stepfunctions', region_name='us-east-1')
        base_url = 'https://console.aws.amazon.com/states/home?region=us-east-1#/executions/details/'
        # build from appropriate input json
        # assume run_type and and run_id
        if 'run_name' in data['config']:
            if _tibanna not in data:
                data[_tibanna] = dict()
            data[_tibanna]['run_name'] = data['config']['run_name']
        data = _tibanna_settings(data, force_inplace=True, env=env)
        run_name = self.randomize_run_name(data[_tibanna]['run_name'], sfn)
        data[_tibanna]['run_name'] = run_name
        data['config']['run_name'] = run_name
        # updated arn
        arn = EXECUTION_ARN(run_name, sfn)
        data[_tibanna]['exec_arn'] = arn
        # calculate what the url will be
        url = "%s%s" % (base_url, arn)
        data[_tibanna]['url'] = url
        # add jobid
        data['jobid'] = jobid
        if 'args' in data:  # unicorn-only
            args = data['args']
            cfg = data['config']
        if ('cwl_directory_local' in args and args['cwl_directory_local']) or \
                ('wdl_directory_local' in args and args['wdl_directory_local']):
            url = upload_workflow_to_s3(args, cfg, jobid)
            if 'language' in args and args['language'] == 'wdl':
                args['wdl_directory_url'] = url
            else:
                args['cwl_directory_url'] = url
        # submit job as an execution
        aws_input = json.dumps(data)
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
        self.add_to_dydb(jobid, run_name, sfn, data['config']['log_bucket'])
        # print some info
        print("response from aws was: \n %s" % response)
        print("url to view status:")
        print(data[_tibanna]['url'])
        data[_tibanna]['response'] = response
        if verbose:
            print("JOBID %s submitted" % data['jobid'])
            print("EXECUTION ARN = %s" % data[_tibanna]['exec_arn'])
            if 'cloudwatch_dashboard' in data['config'] and data['config']['cloudwatch_dashboard']:
                cw_db_url = 'https://console.aws.amazon.com/cloudwatch/' + \
                    'home?region=%s#dashboards:name=awsem-%s' % (AWS_REGION, jobid)
                print("Cloudwatch Dashboard = %s" % cw_db_url)
            if open_browser and shutil.which('open') is not None:
                subprocess.call(["open", data[_tibanna]['url']])
        return data

    def add_to_dydb(self, awsem_job_id, execution_name, sfn, logbucket):
        dydb = boto3.client('dynamodb', region_name=AWS_REGION)
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

    def check_status(self, exec_arn):
        '''checking status of an execution'''
        sts = boto3.client('stepfunctions', region_name=AWS_REGION)
        return sts.describe_execution(executionArn=exec_arn)['status']

    def check_output(self, exec_arn):
        '''checking status of an execution first and if it's success, get output'''
        sts = boto3.client('stepfunctions', region_name=AWS_REGION)
        if self.check_status(exec_arn) == 'SUCCEEDED':
            desc = sts.describe_execution(executionArn=exec_arn)
            if 'output' in desc:
                return json.loads(desc['output'])
            else:
                return None

    def kill(self, exec_arn=None, job_id=None, sfn=None):
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

    def kill_all(self, sfn=None):
        """killing all the running jobs"""
        if not sfn:
            sfn = self.default_stepfunction_name
        client = boto3.client('stepfunctions')
        stateMachineArn = STEP_FUNCTION_ARN(sfn)
        res = client.list_executions(stateMachineArn=stateMachineArn, statusFilter='RUNNING')
        while True:
            if 'executions' not in res or not res['executions']:
                break
            for exc in res['executions']:
                self.kill(exc['executionArn'])
            if 'nextToken' in res:
                res = client.list_executions(nextToken=res['nextToken'],
                                             stateMachineArn=stateMachineArn, statusFilter='RUNNING')
            else:
                break

    def log(self, exec_arn=None, job_id=None, exec_name=None, sfn=None, postrunjson=False):
        if postrunjson:
            suffix = '.postrun.json'
        else:
            suffix = '.log'
        if not sfn:
            sfn = self.default_stepfunction_name
        sf = boto3.client('stepfunctions')
        if not exec_arn and exec_name:
            exec_arn = EXECUTION_ARN(exec_name, sfn)
        if exec_arn:
            desc = sf.describe_execution(executionArn=exec_arn)
            jobid = str(json.loads(desc['input'])['jobid'])
            logbucket = str(json.loads(desc['input'])['config']['log_bucket'])
            res_s3 = boto3.client('s3').get_object(Bucket=logbucket, Key=jobid + suffix)
            if res_s3:
                return(res_s3['Body'].read().decode('utf-8', 'backslashreplace'))
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
                            return(res_s3['Body'].read().decode('utf-8', 'backslashreplace'))
                        break
                if 'nextToken' in res:
                    res = sf.list_executions(nextToken=res['nextToken'],
                                             stateMachineArn=stateMachineArn)
                else:
                    break
        return None

    def stat(self, sfn=None, status=None, verbose=False, n=None):
        """print out executions with details (-v)
        status can be one of 'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'
        """
        if not sfn:
            sfn = self.default_stepfunction_name
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
        k = 0
        while True:
            if n and k == n:
                break
            if 'executions' not in res or not res['executions']:
                break
            for exc in res['executions']:
                if n and k == n:
                    break
                k = k + 1
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

    def list_sfns(self, numbers=False):
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
            if not s['name'].startswith('tibanna_' + self.sfn_type):
                continue
            line = "%s\t%s" % (s['name'], str(s['creationDate']))
            if numbers:
                counts = self.count_status(s['stateMachineArn'], st)
                for status in ['RUNNING', 'SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED_OUT']:
                    line = line + "\t%i" % counts[status]
            print(line)

    def count_status(self, sfn_arn, client):
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

    def clear_input_json_template(self, input_json_template):
        """clear awsem template for reuse"""
        if 'response' in input_json_template['_tibanna']:
            del(input_json_template['_tibanna']['response'])
        if 'run_name' in input_json_template['_tibanna'] and len(input_json_template['_tibanna']['run_name']) > 40:
            input_json_template['_tibanna']['run_name'] = input_json_template['_tibanna']['run_name'][:-36]
            input_json_template['config']['run_name'] = input_json_template['_tibanna']['run_name']

    def rerun(self, exec_arn, sfn=None,
              override_config=None, app_name_filter=None,
              instance_type=None, shutdown_min=None, ebs_size=None, ebs_type=None, ebs_iops=None,
              overwrite_input_extra=None, key_name=None, name=None):
        """rerun a specific job
        override_config : dictionary for overriding config (keys are the keys inside config)
            e.g. override_config = { 'instance_type': 't2.micro' }
        app_name_filter : app_name (e.g. hi-c-processing-pairs), if specified,
        then rerun only if it matches app_name
        """
        if not sfn:
            sfn = self.default_stepfunction_name
        client = boto3.client('stepfunctions')
        res = client.describe_execution(executionArn=exec_arn)
        input_json_template = json.loads(res['input'])
        # filter by app_name
        if app_name_filter:
            if 'app_name' not in input_json_template:
                return(None)
            if input_json_template['app_name'] != app_name_filter:
                return(None)
        self.clear_input_json_template(input_json_template)
        # override config
        if not override_config:
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
        if override_config:
            for k, v in iter(override_config.items()):
                input_json_template['config'][k] = v
        return(self.run_workflow(input_json_template, sfn=sfn))

    def rerun_many(self, sfn=None, stopdate='13Feb2018', stophour=13,
                   stopminute=0, offset=0, sleeptime=5, status='FAILED',
                   override_config=None, app_name_filter=None,
                   instance_type=None, shutdown_min=None, ebs_size=None, ebs_type=None, ebs_iops=None,
                   overwrite_input_extra=None, key_name=None, name=None):
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
        if not sfn:
            sfn = self.default_stepfunction_name
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
                self.rerun(exc['executionArn'], sfn=sfn,
                           override_config=override_config, app_name_filter=app_name_filter,
                           instance_type=instance_type, shutdown_min=shutdown_min, ebs_size=ebs_size,
                           ebs_type=ebs_type, ebs_iops=ebs_iops,
                           overwrite_input_extra=overwrite_input_extra, key_name=key_name, name=name)
                time.sleep(sleeptime)

    def env_list(self, name):
        # don't set this as a global, since not all tasks require it
        envlist = {
            'run_task_awsem': {'AMI_ID_CWL_V1': AMI_ID_CWL_V1,
                               'AMI_ID_CWL_DRAFT3': AMI_ID_CWL_DRAFT3,
                               'AMI_ID_WDL': AMI_ID_WDL,
                               'TIBANNA_REPO_NAME': TIBANNA_REPO_NAME,
                               'TIBANNA_REPO_BRANCH': TIBANNA_REPO_BRANCH,
                               'TIBANNA_AWS_REGION': AWS_REGION,
                               'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
            'check_task_awsem': {'TIBANNA_AWS_REGION': AWS_REGION,
                                 'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER}
        }
        if TIBANNA_PROFILE_ACCESS_KEY and TIBANNA_PROFILE_SECRET_KEY:
            envlist['run_task_awsem'].update({
                'TIBANNA_PROFILE_ACCESS_KEY': TIBANNA_PROFILE_ACCESS_KEY,
                'TIBANNA_PROFILE_SECRET_KEY': TIBANNA_PROFILE_SECRET_KEY}
            )
        return envlist.get(name, '')

    def deploy_lambda(self, name, suffix, usergroup):
        """
        deploy a single lambda using the aws_lambda.deploy_function (BETA)
        """
        import aws_lambda
        if name not in dir(self.lambdas_module):
            raise Exception("Could not find lambda function file for %s" % name)
        lambda_fxn_module = importlib.import_module('.'.join([self.lambdas_module.__name__,  name]))
        requirements_fpath = os.path.join(self.lambdas_module.__path__[0], 'requirements.txt')
        # add extra config to the lambda deployment
        extra_config = {}
        envs = self.env_list(name)
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
        aws_lambda.deploy_function(lambda_fxn_module,
                                   function_name_suffix=suffix,
                                   package_objects=self.tibanna_packages,
                                   requirements_fpath=requirements_fpath,
                                   extra_config=extra_config)

    def deploy_core(self, name, suffix=None, usergroup=None):
        """deploy/update lambdas only"""
        print("preparing for deploy...")
        if name == 'all':
            names = self.lambda_names
        elif name == 'unicorn':
            names = UNICORN_LAMBDAS
        else:
            names = [name, ]
        for name in names:
            self.deploy_lambda(name, suffix, usergroup)

    def setup_tibanna_env(self, buckets='', usergroup_tag='default', no_randomize=False, verbose=False):
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

    def deploy_tibanna(self, suffix=None, usergroup=None, setup=False,
                       buckets='', setenv=False):
        """deploy tibanna unicorn or pony to AWS cloud (pony is for 4DN-DCIC only)"""
        if setup:
            if usergroup:
                usergroup = self.setup_tibanna_env(buckets, usergroup, True)
            else:
                usergroup = self.setup_tibanna_env(buckets)  # override usergroup
        print("creating a new step function...")
        # this function will remove existing step function on a conflict
        step_function_name = self.create_stepfunction(suffix, usergroup=usergroup)
        if setenv:
            os.environ['TIBANNA_DEFAULT_STEP_FUNCTION_NAME'] = step_function_name
            with open(os.getenv('HOME') + "/.bashrc", "a") as outfile:  # 'a' stands for "append"
                outfile.write("\nexport TIBANNA_DEFAULT_STEP_FUNCTION_NAME=%s\n" % step_function_name)
        print("deploying lambdas...")
        self.deploy_core('all', suffix=suffix, usergroup=usergroup)
        return step_function_name

    def deploy_unicorn(self, suffix=None, no_setup=False, buckets='',
                       no_setenv=False, usergroup=None):
        """deploy tibanna unicorn to AWS cloud"""
        self.deploy_tibanna(suffix=suffix, usergroup=usergroup, setup=not no_setup,
                            buckets=buckets, setenv=not no_setenv)

    def add_user(self, user, usergroup):
        """add a user to a tibanna group"""
        boto3.client('iam').add_user_to_group(
            GroupName='tibanna_' + usergroup,
            UserName=user
        )

    def users(self):
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

    def create_stepfunction(self, dev_suffix=None,
                            region_name=AWS_REGION,
                            aws_acc=AWS_ACCOUNT_NUMBER,
                            usergroup=None):
        if not aws_acc or not region_name:
            print("Please set and export environment variable AWS_ACCOUNT_NUMBER and AWS_REGION!")
            exit(1)
        # create a step function definition object
        sfndef = self.StepFunction(dev_suffix, region_name, aws_acc, usergroup)
        # if this encouters an existing step function with the same name, delete
        sfn = boto3.client('stepfunctions', region_name=region_name)
        retries = 12  # wait 10 seconds between retries for total of 120s
        for i in range(retries):
            try:
                sfn.create_state_machine(
                    name=sfndef.sfn_name,
                    definition=json.dumps(sfndef.definition, indent=4, sort_keys=True),
                    roleArn=sfndef.sfn_role_arn
                )
            except sfn.exceptions.StateMachineAlreadyExists as e:
                # get ARN from the error and format as necessary
                exc_str = str(e)
                if 'State Machine Already Exists:' not in exc_str:
                    print('Cannot delete state machine. Exiting...' % exc_str)
                    raise(e)
                sfn_arn = exc_str.split('State Machine Already Exists:')[-1].strip().strip("''")
                print('Step function with name %s already exists!' % sfndef.sfn_name)
                print('Updating the state machine...')
                try:
                    sfn.update_state_machine(
                        stateMachineArn=sfn_arn,
                        definition=json.dumps(sfndef.definition, indent=4, sort_keys=True),
                        roleArn=sfndef.sfn_role_arn
                    )
                except Exception as e:
                    print('Error updating state machine %s' % str(e))
                    raise(e)
            except Exception as e:
                raise(e)
            break
        return sfndef.sfn_name
