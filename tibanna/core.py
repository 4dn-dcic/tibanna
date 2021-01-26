# -*- coding: utf-8 -*-
import os
import boto3
import json
import time
import copy
import importlib
import shutil
import subprocess
import webbrowser
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from uuid import uuid4, UUID
from types import ModuleType
from . import create_logger
from .vars import (
    _tibanna,
    AWS_ACCOUNT_NUMBER,
    AWS_REGION,
    TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
    STEP_FUNCTION_ARN,
    EXECUTION_ARN,
    AMI_ID,
    TIBANNA_REPO_NAME,
    TIBANNA_REPO_BRANCH,
    TIBANNA_PROFILE_ACCESS_KEY,
    TIBANNA_PROFILE_SECRET_KEY,
    METRICS_URL,
    DYNAMODB_TABLE,
    DYNAMODB_KEYNAME,
    SFN_TYPE,
    LAMBDA_TYPE,
    RUN_TASK_LAMBDA_NAME,
    CHECK_TASK_LAMBDA_NAME
)
from .utils import (
    _tibanna_settings,
    create_jobid,
    does_key_exist,
    read_s3,
    upload,
    retrieve_all_keys,
    delete_keys
)
from .ec2_utils import (
    UnicornInput,
    upload_workflow_to_s3
)
from .ami import AMI
# from botocore.errorfactory import ExecutionAlreadyExists
from .stepfunction import StepFunctionUnicorn
from .awsem import AwsemRunJson, AwsemPostRunJson
from .exceptions import (
    MetricRetrievalException
)
from . import dd_utils


# logger
logger = create_logger(__name__)


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
    sfn_type = SFN_TYPE
    lambda_type = LAMBDA_TYPE

    run_task_lambda = RUN_TASK_LAMBDA_NAME
    check_task_lambda = CHECK_TASK_LAMBDA_NAME

    @property
    def UNICORN_LAMBDAS(self):
        return [self.run_task_lambda, self.check_task_lambda]

    @property
    def do_not_delete(self):
        return []  # list of lambda names that should not be deleted before updating

    @property
    def TibannaResource(self):
        from .cw_utils import TibannaResource
        return TibannaResource

    @property
    def IAM(self):
        from .iam_utils import IAM
        return IAM

    def __init__(self):
        pass

    def randomize_run_name(self, run_name, sfn):
        arn = EXECUTION_ARN(run_name, sfn)
        client = boto3.client('stepfunctions', region_name=AWS_REGION)
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
        if len(run_name) > 80:
            run_name = run_name[:79]
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
        client = boto3.client('stepfunctions', region_name=AWS_REGION)
        base_url = 'https://console.aws.amazon.com/states/home?region=' + AWS_REGION + '#/executions/details/'
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
            unicorn_input = UnicornInput(data)
            args = unicorn_input.args
            if args.language.startswith('cwl') and args.cwl_directory_local or \
               args.language in ['wdl', 'wdl_v1', 'wdl_draft2'] and args.wdl_directory_local or \
               args.language == 'snakemake' and args.snakemake_directory_local:
                upload_workflow_to_s3(unicorn_input)
                data['args'] = args.as_dict()  # update args
        # submit job as an execution
        aws_input = json.dumps(data)
        if verbose:
            logger.info("about to start run %s" % run_name)
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
        self.add_to_dydb(jobid, run_name, sfn, data['config']['log_bucket'], verbose=verbose)
        data[_tibanna]['response'] = response
        if verbose:
            # print some info
            logger.info("response from aws was: \n %s" % response)
            logger.info("url to view status:")
            logger.info(data[_tibanna]['url'])
            logger.info("JOBID %s submitted" % data['jobid'])
            logger.info("EXECUTION ARN = %s" % data[_tibanna]['exec_arn'])
            if 'cloudwatch_dashboard' in data['config'] and data['config']['cloudwatch_dashboard']:
                cw_db_url = 'https://console.aws.amazon.com/cloudwatch/' + \
                    'home?region=%s#dashboards:name=awsem-%s' % (AWS_REGION, jobid)
                logger.info("Cloudwatch Dashboard = %s" % cw_db_url)
            if open_browser and shutil.which('open') is not None:
                subprocess.call(["open", data[_tibanna]['url']])
        return data

    def run_batch_workflows(self, input_json_list, sfn=None,
                     env=None, sleep=3, verbose=True, open_browser=True):
        """given a list of input json, run multiple workflows"""
        run_infos = []
        for input_json in input_json_list:
            run_info = self.run_workflow(input_json, env=env, sfn=sfn, sleep=sleep, verbose=verbose,
                       open_browser=False)
            run_infos.append(run_info)
        return run_infos

    def add_to_dydb(self, awsem_job_id, execution_name, sfn, logbucket, verbose=True):
        time_stamp = datetime.strftime(datetime.utcnow(), '%Y%m%d-%H:%M:%S-UTC')
        dydb = boto3.client('dynamodb', region_name=AWS_REGION)
        try:
            # first check the table exists
            res = dydb.describe_table(TableName=DYNAMODB_TABLE)
        except Exception as e:
            if verbose:
                logger.info("Not adding to dynamo table: %s" % e)
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
                    'Time Stamp': {
                        'S': time_stamp
                    }
                }
            )
            if verbose:
                logger.info("Successfully put item to dynamoDB: " + str(response))
        except Exception as e:
            raise(e)

    def check_status(self, exec_arn=None, job_id=None):
        '''checking status of an execution.
        It works only if the execution info is still in the step function.'''
        if not exec_arn and job_id:
            ddinfo = self.info(job_id)
            if not ddinfo:
                raise Exception("Can't find exec_arn from the job_id")
            exec_name = ddinfo.get('Execution Name', '')
            sfn = ddinfo.get('Step Function', '')
            exec_arn = EXECUTION_ARN(exec_name, sfn)
            if not exec_arn:
                raise Exception("Can't find exec_arn from the job_id")
        sts = boto3.client('stepfunctions', region_name=AWS_REGION)
        return sts.describe_execution(executionArn=exec_arn)['status']

    def check_output(self, exec_arn=None, job_id=None):
        '''checking status of an execution first and if it's success, get output.
        It works only if the execution info is still in the step function.'''
        if not exec_arn and job_id:
            ddinfo = self.info(job_id)
            if not ddinfo:
                raise Exception("Can't find exec_arn from the job_id")
            exec_name = ddinfo.get('Execution Name', '')
            sfn = ddinfo.get('Step Function', '')
            exec_arn = EXECUTION_ARN(exec_name, sfn)
            if not exec_arn:
                raise Exception("Can't find exec_arn from the job_id")
        sts = boto3.client('stepfunctions', region_name=AWS_REGION)
        if self.check_status(exec_arn) == 'SUCCEEDED':
            desc = sts.describe_execution(executionArn=exec_arn)
            if 'output' in desc:
                return json.loads(desc['output'])
            else:
                return None

    def get_dd(self, job_id):
        '''return raw content from dynamodb for a given job id'''
        ddres = dict()
        try:
            dd = boto3.client('dynamodb')
            ddres = dd.query(TableName=DYNAMODB_TABLE,
                             KeyConditions={'Job Id': {'AttributeValueList': [{'S': job_id}],
                                                       'ComparisonOperator': 'EQ'}})
            return ddres
        except Exception as e:
            logger.warning("DynamoDB entry not found: %s" % e)
            return None

    def info(self, job_id):
        '''returns content from dynamodb for a given job id in a dictionary form'''
        ddres = self.get_dd(job_id)
        return self.get_info_from_dd(ddres)

    def get_info_from_dd(self, ddres):
        '''converts raw content from dynamodb to a dictionary form'''
        if not ddres:
            return None
        if 'Items' in ddres:
            try:
                dditem = ddres['Items'][0]
                return dd_utils.item2dict(dditem)
            except Exception as e:
                logger.warning("DynamoDB fields not found: %s" % e)
                return None
        else:
            logger.warning("DynamoDB Items field not found:")
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
                                logger.info("terminating EC2 instance")
                                response = i.terminate()
                                logger.info("Successfully terminated instance: " + str(response))
                                terminated = True
                                break
                        if terminated:
                            break
                logger.info("terminating step function execution")
                resp_sf = sf.stop_execution(executionArn=exec_arn, error="Aborted")
                logger.info("Successfully terminated step function execution: " + str(resp_sf))
        elif job_id:
            ec2 = boto3.client('ec2')
            res = ec2.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': ['awsem-' + job_id]}])
            if not res['Reservations']:
                raise("instance not available - if you just submitted the job, try again later")
            instance_id = res['Reservations'][0]['Instances'][0]['InstanceId']
            logger.info("terminating EC2 instance")
            resp_term = ec2.terminate_instances(InstanceIds=[instance_id])
            logger.info("Successfully terminated instance: " + str(resp_term))
            # first try dynanmodb to get logbucket
            ddres = dict()
            try:
                dd = boto3.client('dynamodb')
                ddres = dd.query(TableName=DYNAMODB_TABLE,
                                 KeyConditions={'Job Id': {'AttributeValueList': [{'S': job_id}],
                                                           'ComparisonOperator': 'EQ'}})
            except Exception as e:
                pass
            if 'Items' in ddres:
                exec_name = ddres['Items'][0]['Execution Name']['S']
                sfn = ddres['Items'][0]['Step Function']['S']
                exec_arn = EXECUTION_ARN(exec_name, sfn)
            else:
                if not sfn:
                    logger.warning("Can't stop step function because step function name is not given.")
                    return None
                stateMachineArn = STEP_FUNCTION_ARN(sfn)
                res = sf.list_executions(stateMachineArn=stateMachineArn, statusFilter='RUNNING')
                exec_arn = None
                while True:
                    if 'executions' not in res or not res['executions']:
                        break
                    for exc in res['executions']:
                        desc = sf.describe_execution(executionArn=exc['executionArn'])
                        if job_id == str(json.loads(desc['input'])['jobid']):
                            exec_arn = exc['executionArn']
                            break
                    if exec_arn:
                        break
                    if 'nextToken' in res:
                        res = sf.list_executions(nextToken=res['nextToken'],
                                                 stateMachineArn=stateMachineArn, statusFilter='RUNNING')
                    else:
                        break
                if not exec_arn:
                    raise Exception("can't find the execution")
            logger.info("terminating step function execution")
            resp_sf = sf.stop_execution(executionArn=exec_arn, error="Aborted")
            logger.info("Successfully terminated step function execution: " + str(resp_sf))

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

    def log(self, exec_arn=None, job_id=None, exec_name=None, sfn=None,
            postrunjson=False, runjson=False, top=False, top_latest=False,
            inputjson=False, logbucket=None, quiet=False):
        if postrunjson:
            suffix = '.postrun.json'
        elif runjson:
            suffix = '.run.json'
        elif top:
            suffix = '.top'
        elif top_latest:
            suffix = '.top_latest'
        elif inputjson:
            suffix = '.input.json'
        else:
            suffix = '.log'
        if not sfn:
            sfn = self.default_stepfunction_name
        sf = boto3.client('stepfunctions')
        if not exec_arn and exec_name:
            exec_arn = EXECUTION_ARN(exec_name, sfn)
        if exec_arn:
            desc = sf.describe_execution(executionArn=exec_arn)
            job_id = str(json.loads(desc['input'])['jobid'])
            if not logbucket:
                logbucket = str(json.loads(desc['input'])['config']['log_bucket'])
        elif job_id:
            if not logbucket:
                # first try dynanmodb to get logbucket
                try:
                    logbucket = self.info(job_id)['Log Bucket']
                except Exception as e:
                    pass
                if not logbucket:
                    # search through executions to get logbucket
                    stateMachineArn = STEP_FUNCTION_ARN(sfn)
                    try:
                        res = sf.list_executions(stateMachineArn=stateMachineArn)
                        while True:
                            if 'executions' not in res or not res['executions']:
                                break
                            breakwhile = False
                            for exc in res['executions']:
                                desc = sf.describe_execution(executionArn=exc['executionArn'])
                                if job_id == str(json.loads(desc['input'])['jobid']):
                                    logbucket = str(json.loads(desc['input'])['config']['log_bucket'])
                                    breakwhile = True
                                    break
                            if breakwhile:
                                break
                            if 'nextToken' in res:
                                res = sf.list_executions(nextToken=res['nextToken'],
                                                         stateMachineArn=stateMachineArn)
                            else:
                                break
                    except:
                        raise Exception("Cannot retrieve job. Try again later.")
        else:
            raise Exception("Either job_id, exec_arn or exec_name must be provided.")
        try:
            res_s3 = boto3.client('s3').get_object(Bucket=logbucket, Key=job_id + suffix)
        except Exception as e:
            if 'NoSuchKey' in str(e):
                if not quiet:
                    logger.info("log/postrunjson file is not ready yet. " +
                                "Wait a few seconds/minutes and try again.")
                return ''
            else:
                raise e
        if res_s3:
            return(res_s3['Body'].read().decode('utf-8', 'backslashreplace'))
        return None

    def stat(self, sfn=None, status=None, verbose=False, n=None, job_ids=None):
        """print out executions with details (-v)
        status can be one of 'RUNNING'|'SUCCEEDED'|'FAILED'|'TIMED_OUT'|'ABORTED'
        or specify a list of job ids
        """
        if n and job_ids:
            raise Exception("n and job_id filters do not work together.")
        if sfn and job_ids:
            raise Exception("Please do not specify sfn when job_ids are specified.")
        if status and job_ids:
            raise Exception("Status filter cannot be specified when job_ids are specified.")
        if verbose:
            print("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format('jobid', 'status', 'name',
                                                                      'start_time', 'stop_time',
                                                                      'instance_id', 'instance_type',
                                                                      'instance_status', 'ip', 'key',
                                                                      'password'))
        else:
            print("{}\t{}\t{}\t{}\t{}".format('jobid', 'status', 'name', 'start_time', 'stop_time'))
        client = boto3.client('stepfunctions')
        ec2 = boto3.client('ec2')

        def parse_exec_desc_and_ec2_desc(exec_arn, verbose):
            # collecting execution stats
            exec_desc = client.describe_execution(executionArn=exec_arn)

            # getting info from execution description
            exec_desc = client.describe_execution(executionArn=exec_arn)
            job_id = json.loads(exec_desc['input']).get('jobid', 'no jobid')
            status = exec_desc['status']
            name = exec_desc['name']
            start_time = exec_desc['startDate'].strftime("%Y-%m-%d %H:%M")
            if 'stopDate' in exec_desc:
                stop_time = exec_desc['stopDate'].strftime("%Y-%m-%d %H:%M")
            else:
                stop_time = ''

            # collect instance stats
            ec2_desc = ec2.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': ['awsem-' + job_id]}])

            # getting info from ec2 description
            if ec2_desc['Reservations']:
                ec2_desc_inst = ec2_desc['Reservations'][0]['Instances'][0]
                instance_status = ec2_desc_inst['State']['Name']
                instance_id = ec2_desc_inst['InstanceId']
                instance_type = ec2_desc_inst['InstanceType']
                if instance_status not in ['terminated', 'shutting-down']:
                    instance_ip = ec2_desc_inst.get('PublicIpAddress', '-')
                    keyname = ec2_desc_inst.get('KeyName', '-')
                    password = json.loads(exec_desc['input'])['config'].get('password', '-')
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

            parsed_stat = (job_id, status, name, start_time, stop_time,
                           instance_id, instance_type, instance_status,
                           instance_ip, keyname, password)
            if verbose:
                print("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(*parsed_stat))
            else:
                print("{}\t{}\t{}\t{}\t{}".format(*parsed_stat[0:5]))

        if job_ids:
            for job_id in job_ids:
                dd_info = self.info(job_id)
                if 'Execution Name' not in dd_info:
                    raise Exception("Cannot find execution name for job ID %s" % job_id)
                if 'Step Function' not in dd_info:
                    raise Exception("Cannot find step function for job ID %s" % job_id)
                exec_arn = EXECUTION_ARN(dd_info['Execution Name'], dd_info['Step Function'])
                parse_exec_desc_and_ec2_desc(exec_arn, verbose)
        else:
            if not sfn:
                sfn = self.default_stepfunction_name
            args = {
                'stateMachineArn': STEP_FUNCTION_ARN(sfn),
                'maxResults': 100
            }
            if status:
                args['statusFilter'] = status
            res = dict()
            res = client.list_executions(**args)
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
                    parse_exec_desc_and_ec2_desc(exc['executionArn'], verbose)
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

    def rerun(self, exec_arn=None, job_id=None, sfn=None,
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
            sfn = self.default_stepfunction_name  # this is a target sfn
        if not exec_arn and job_id:
            input_json_template = json.loads(self.log(job_id=job_id, inputjson=True))
        else:
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
            self.run_task_lambda: {'AMI_ID': AMI_ID,
                                   'TIBANNA_REPO_NAME': TIBANNA_REPO_NAME,
                                   'TIBANNA_REPO_BRANCH': TIBANNA_REPO_BRANCH},
            self.check_task_lambda: {}
        }
        if TIBANNA_PROFILE_ACCESS_KEY and TIBANNA_PROFILE_SECRET_KEY:
            envlist[self.run_task_lambda].update({
                'TIBANNA_PROFILE_ACCESS_KEY': TIBANNA_PROFILE_ACCESS_KEY,
                'TIBANNA_PROFILE_SECRET_KEY': TIBANNA_PROFILE_SECRET_KEY}
            )
        return envlist.get(name, '')

    def deploy_lambda(self, name, suffix, usergroup=''):
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
        tibanna_iam = self.IAM(usergroup)
        if name == self.run_task_lambda:
            if usergroup:
                extra_config['Environment']['Variables']['AWS_S3_ROLE_NAME'] \
                    = tibanna_iam.role_name('ec2')
            else:
                extra_config['Environment']['Variables']['AWS_S3_ROLE_NAME'] = 'S3_access'  # 4dn-dcic default(temp)
        # add role
        logger.info('name=%s' % name)
        if name in [self.run_task_lambda, self.check_task_lambda]:
            role_arn_prefix = 'arn:aws:iam::' + AWS_ACCOUNT_NUMBER + ':role/'
            if usergroup:
                role_arn = role_arn_prefix + tibanna_iam.role_name(name)
            else:
                role_arn = role_arn_prefix + 'lambda_full_s3'  # 4dn-dcic default(temp)
            logger.info("role_arn=" + role_arn)
            extra_config['Role'] = role_arn
        if usergroup and suffix:
            function_name_suffix = usergroup + '_' + suffix
        elif suffix:
            function_name_suffix = suffix
        elif usergroup:
            function_name_suffix = usergroup
        else:
            function_name_suffix = ''
        # first delete the existing function to avoid the weird AWS KMS lambda error
        function_name_prefix = getattr(self.lambdas_module, name).config.get('function_name')
        if function_name_suffix:
            full_function_name = function_name_prefix + '_' + function_name_suffix
        else:
            full_function_name = function_name_prefix
        if name not in self.do_not_delete:
            try:
                boto3.client('lambda').get_function(FunctionName=full_function_name)
                logger.info("deleting existing lambda")
                boto3.client('lambda').delete_function(FunctionName=full_function_name)
            except Exception as e:
                if 'Function not found' in str(e):
                    pass
        aws_lambda.deploy_function(lambda_fxn_module,
                                   function_name_suffix=function_name_suffix,
                                   package_objects=self.tibanna_packages,
                                   requirements_fpath=requirements_fpath,
                                   extra_config=extra_config)

    def deploy_core(self, name, suffix=None, usergroup=''):
        """deploy/update lambdas only"""
        logger.info("preparing for deploy...")
        if name == 'all':
            names = self.lambda_names
        elif name == 'unicorn':
            names = self.UNICORN_LAMBDAS
        else:
            names = [name, ]
        for name in names:
            self.deploy_lambda(name, suffix, usergroup)

    def setup_tibanna_env(self, buckets='', usergroup_tag='default', no_randomize=False,
                          do_not_delete_public_access_block=False, verbose=False):
        """set up usergroup environment on AWS
        This function is called automatically by deploy_tibanna or deploy_unicorn
        Use it only when the IAM permissions need to be reset"""
        logger.info("setting up tibanna usergroup environment on AWS...")
        if not AWS_ACCOUNT_NUMBER or not AWS_REGION:
            logger.info("Please set and export environment variable AWS_ACCOUNT_NUMBER and AWS_REGION!")
            exit(1)
        if not buckets:
            logger.warning("Without setting buckets (using --buckets)," +
                           "Tibanna would have access to only public buckets." +
                           "To give permission to Tibanna for private buckets," +
                           "use --buckets=<bucket1>,<bucket2>,...")
            time.sleep(2)
        if buckets:
            bucket_names = buckets.split(',')
        else:
            bucket_names = None
        if bucket_names and not do_not_delete_public_access_block:
            client = boto3.client('s3')
            for b in bucket_names:
                logger.info("Deleting public access block for bucket %s" % b)
                response = client.delete_public_access_block(Bucket=b)
        tibanna_iam = self.IAM(usergroup_tag, bucket_names, no_randomize=no_randomize)
        tibanna_iam.create_tibanna_iam(verbose=verbose)
        logger.info("Tibanna usergroup %s has been created on AWS." % tibanna_iam.user_group_name)
        return tibanna_iam.user_group_name

    def deploy_tibanna(self, suffix=None, usergroup='', setup=False,
                       buckets='', setenv=False, do_not_delete_public_access_block=False):
        """deploy tibanna unicorn or pony to AWS cloud (pony is for 4DN-DCIC only)"""
        if setup:
            if usergroup:
                usergroup = self.setup_tibanna_env(buckets, usergroup, True,
                            do_not_delete_public_access_block=do_not_delete_public_access_block)
            else:  # override usergroup
                usergroup = self.setup_tibanna_env(buckets,
                            do_not_delete_public_access_block=do_not_delete_public_access_block)
        # this function will remove existing step function on a conflict
        step_function_name = self.create_stepfunction(suffix, usergroup=usergroup)
        logger.info("creating a new step function... %s" % step_function_name)
        if setenv:
            os.environ['TIBANNA_DEFAULT_STEP_FUNCTION_NAME'] = step_function_name
            with open(os.getenv('HOME') + "/.bashrc", "a") as outfile:  # 'a' stands for "append"
                outfile.write("\nexport TIBANNA_DEFAULT_STEP_FUNCTION_NAME=%s\n" % step_function_name)
        logger.info("deploying lambdas...")
        self.deploy_core('all', suffix=suffix, usergroup=usergroup)
        dd_utils.create_dynamo_table(DYNAMODB_TABLE, DYNAMODB_KEYNAME)
        return step_function_name

    def deploy_unicorn(self, suffix=None, no_setup=False, buckets='',
                       no_setenv=False, usergroup='', do_not_delete_public_access_block=False):
        """deploy tibanna unicorn to AWS cloud"""
        self.deploy_tibanna(suffix=suffix, usergroup=usergroup, setup=not no_setup,
                            buckets=buckets, setenv=not no_setenv,
                            do_not_delete_public_access_block=do_not_delete_public_access_block)

    def add_user(self, user, usergroup):
        """add a user to a tibanna group"""
        groupname_prefix = 'tibanna_'
        if self.lambda_type:
            groupname_prefix += self.lambda_type + '_'
        boto3.client('iam').add_user_to_group(
            GroupName=groupname_prefix + usergroup,
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
            logger.info("Please set and export environment variable AWS_ACCOUNT_NUMBER and AWS_REGION!")
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
                    logger.error('Cannot delete state machine. Exiting...' % exc_str)
                    raise(e)
                sfn_arn = exc_str.split('State Machine Already Exists:')[-1].strip().strip("''")
                logger.info('Step function with name %s already exists!' % sfndef.sfn_name)
                logger.info('Updating the state machine...')
                try:
                    sfn.update_state_machine(
                        stateMachineArn=sfn_arn,
                        definition=json.dumps(sfndef.definition, indent=4, sort_keys=True),
                        roleArn=sfndef.sfn_role_arn
                    )
                except Exception as e:
                    logger.error('Error updating state machine %s' % str(e))
                    raise(e)
            except Exception as e:
                raise(e)
            break
        return sfndef.sfn_name

    def check_metrics_plot(self, job_id, log_bucket):
        return True if does_key_exist(log_bucket, job_id + '.metrics/metrics.html', quiet=True) else False

    def check_metrics_lock(self, job_id, log_bucket):
        return True if does_key_exist(log_bucket, job_id + '.metrics/lock', quiet=True) else False

    def plot_metrics(self, job_id, sfn=None, directory='.', open_browser=True, force_upload=False,
                     update_html_only=False, endtime='', filesystem='/dev/nvme1n1', instance_id=''):
        ''' retrieve instance_id and plots metrics '''
        if not sfn:
            sfn = self.default_stepfunction_name
        postrunjsonstr = self.log(job_id=job_id, sfn=sfn, postrunjson=True, quiet=True)
        if postrunjsonstr:
            postrunjson = AwsemPostRunJson(**json.loads(postrunjsonstr))
            job = postrunjson.Job
            if hasattr(job, 'end_time_as_str') and job.end_time_as_str:
                job_complete = True
            else:
                job_complete = False
            log_bucket = postrunjson.config.log_bucket
            instance_type = postrunjson.config.instance_type or 'unknown'
        else:
            runjsonstr = self.log(job_id=job_id, sfn=sfn, runjson=True, quiet=True)
            job_complete = False
            if runjsonstr:
                runjson = AwsemRunJson(**json.loads(runjsonstr))
                job = runjson.Job
                log_bucket = runjson.config.log_bucket
                instance_type = runjson.config.instance_type or 'unknown'
            else:
                raise Exception("Neither postrun json nor run json can be retrieved." +
                                "Check job_id or step function?")
        # report already on s3 with a lock
        if self.check_metrics_plot(job_id, log_bucket) and \
           self.check_metrics_lock(job_id, log_bucket) and \
           not force_upload:
            logger.info("Metrics plot is already on S3 bucket.")
            logger.info('metrics url= ' + METRICS_URL(log_bucket, job_id))
            # open metrics html in browser
            if open_browser:
                webbrowser.open(METRICS_URL(log_bucket, job_id))
            return None
        # report not already on s3 with a lock
        starttime = job.start_time_as_str
        if not endtime:
            if hasattr(job, 'end_time_as_str') and job.end_time_as_str:
                endtime = job.end_time_as_str
            else:
                endtime = datetime.utcnow()
        if hasattr(job, 'filesystem') and job.filesystem:
            filesystem = job.filesystem
        else:
            filesystem = filesystem
        if not instance_id:
            if hasattr(job, 'instance_id') and job.instance_id:
                instance_id = job.instance_id
            else:
                ddres = dict()
                try:
                    dd = boto3.client('dynamodb')
                    ddres = dd.query(TableName=DYNAMODB_TABLE,
                                     KeyConditions={'Job Id': {'AttributeValueList': [{'S': job_id}],
                                                               'ComparisonOperator': 'EQ'}})
                except Exception as e:
                    pass
                if 'Items' in ddres:
                    instance_id = ddres['Items'][0].get('instance_id', {}).get('S', '')
                if not instance_id:
                    ec2 = boto3.client('ec2')
                    res = ec2.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': ['awsem-' + job_id]}])
                    if res['Reservations']:
                        instance_id = res['Reservations'][0]['Instances'][0]['InstanceId']
                        instance_status = res['Reservations'][0]['Instances'][0]['State']['Name']
                        if instance_status in ['terminated', 'shutting-down']:
                            job_complete = True  # job failed
                        else:
                            job_complete = False  # still running
                    else:
                        # waiting 10 min to be sure the istance is starting
                        if (datetime.utcnow() - starttime) / timedelta(minutes=1) < 5:
                            raise Exception("the instance is still setting up. " +
                                            "Wait a few seconds/minutes and try again.")
                        else:
                            raise Exception("instance id not available for this run. Try manually providing " + \
                                            "it using the instance_id parameter (--instance-id option)")
        # plotting
        if update_html_only:
            self.TibannaResource.update_html(log_bucket, job_id + '.metrics/')
        else:
            try:
                M = self.TibannaResource(instance_id, filesystem, starttime, endtime)
                top_content = self.log(job_id=job_id, top=True)
                M.plot_metrics(instance_type, directory, top_content=top_content)
            except Exception as e:
                raise MetricRetrievalException(e)
            # upload files
            M.upload(bucket=log_bucket, prefix=job_id + '.metrics/', lock=job_complete)
            # clean up uploaded files
            for f in M.list_files:
                os.remove(f)
        logger.info('metrics url= ' + METRICS_URL(log_bucket, job_id))
        # open metrics html in browser
        if open_browser:
            webbrowser.open(METRICS_URL(log_bucket, job_id))

    def cost(self, job_id, sfn=None, update_tsv=False):
        if not sfn:
            sfn = self.default_stepfunction_name
        postrunjsonstr = self.log(job_id=job_id, sfn=sfn, postrunjson=True)
        if not postrunjsonstr:
            return None
        postrunjson = AwsemPostRunJson(**json.loads(postrunjsonstr))
        job = postrunjson.Job

        def reformat_time(t, delta):
            d = datetime.strptime(t, '%Y%m%d-%H:%M:%S-UTC') + timedelta(days=delta)
            return d.strftime("%Y-%m-%d")

        start_time = reformat_time(job.start_time, -1)  # give more room
        end_time = reformat_time(job.end_time, 1)  # give more room
        billing_args = {'Filter': {'Tags': {'Key': 'Name', 'Values': ['awsem-' + job_id]}},
                        'Granularity': 'DAILY',
                        'TimePeriod': {'Start': start_time,
                                       'End': end_time},
                        'Metrics': ['BlendedCost']}
        billingres = boto3.client('ce').get_cost_and_usage(**billing_args)
        cost = sum([float(_['Total']['BlendedCost']['Amount']) for _ in billingres['ResultsByTime']])
        if update_tsv:
            log_bucket = postrunjson.config.log_bucket
            # reading from metrics_report.tsv
            does_key_exist(log_bucket, job_id + '.metrics/metrics_report.tsv')
            read_file = read_s3(log_bucket, os.path.join(job_id + '.metrics/', 'metrics_report.tsv'))
            if 'Cost' not in read_file:
                write_file = read_file + 'Cost\t' + str(cost) + '\n'
                # writing
                with open('metrics_report.tsv', 'w') as fo:
                    fo.write(write_file)
                # upload new metrics_report.tsv
                upload('metrics_report.tsv', log_bucket, job_id + '.metrics/')
                os.remove('metrics_report.tsv')
            else:
                logger.info("cost already in the tsv file. not updating")
        return cost

    def does_dynamo_table_exist(self, tablename):
        try:
            res = boto3.client('dynamodb').describe_table(
                TableName=tablename
            )
            if res:
                return True
            else:
                raise Exception("error describing table %s" % tablename)
        except Exception as e:
            if 'Requested resource not found' in str(e):
                return False
            else:
                raise Exception("error describing table %s" % tablename)

    def create_dynamo_table(self, tablename, keyname):
        if self.does_dynamo_table_exist(tablename):
            logger.info("dynamodb table %s already exists. skip creating db" % tablename)
        else:
            response = boto3.client('dynamodb').create_table(
                TableName=tablename,
                AttributeDefinitions=[
                    {
                         'AttributeName': keyname,
                         'AttributeType': 'S'
                    }
                ],
                KeySchema=[
                    {
                        'AttributeName': keyname,
                        'KeyType': 'HASH'
                     }
                ],
                BillingMode='PAY_PER_REQUEST'
            )

    def is_idle(self, instance_id, max_cpu_percent_threshold=1.0):
        """returns True if the instance is idle i.e. not doing anything for
        the past 1 hour and is safe to kill"""
        end = datetime.now(tzutc())
        start = end - timedelta(hours=1)
        filesystem = '/dev/nvme1n1'  # doesn't matter for cpu utilization
        try:
            cw_res = self.TibannaResource(instance_id, filesystem, start, end).as_dict()
        except Exception as e:
            raise MetricRetrievalException(e)
        if not cw_res['max_cpu_utilization_percent']:
            return True
        if cw_res['max_cpu_utilization_percent'] < max_cpu_percent_threshold:
            return True
        return False

    def cleanup(self, user_group_name, suffix='', ignore_errors=True, do_not_remove_iam_group=False,
                purge_history=False, verbose=False):

        def handle_error(errmsg):
            if ignore_errors:
                if verbose:
                    logger.warning(errmsg)
                    logger.info("continue to remove the other components")
            else:
                raise Exception(errmsg)

        if user_group_name.startswith('tibanna_'):
            raise Exception("User_group_name does not start with tibanna or tibanna_unicorn.")
        if suffix:
            lambda_suffix = '_' + user_group_name + '_' + suffix
        else:
            lambda_suffix = '_' + user_group_name
        # delete step function
        sfn = 'tibanna_' + self.sfn_type + lambda_suffix
        if verbose:
            logger.info("deleting step function %s" % sfn)
        try:
            boto3.client('stepfunctions').delete_state_machine(stateMachineArn=STEP_FUNCTION_ARN(sfn))
        except Exception as e:
            handle_error("Failed to cleanup step function: %s" % str(e))
        # delete lambdas
        lambda_client = boto3.client('lambda')
        for lmb in self.lambda_names:
            if verbose:
                logger.info("deleting lambda functions %s" % lmb + lambda_suffix)
            try:
                lambda_client.delete_function(FunctionName=lmb + lambda_suffix)
            except Exception as e:
                handle_error("Failed to cleanup lambda: %s" % str(e))
        # delete IAM policies, roles and groups
        if not do_not_remove_iam_group:
            if verbose:
                logger.info("deleting IAM permissions %s" % sfn)
            iam = self.IAM(user_group_name)
            iam.delete_tibanna_iam(verbose=verbose, ignore_errors=ignore_errors)
        if purge_history:
            if verbose:
                logger.info("deleting all job files and history")
            item_list = dd_utils.get_items(DYNAMODB_TABLE, DYNAMODB_KEYNAME, 'Step Function', sfn, ['Log Bucket'])
            for item in item_list:
                jobid = item[DYNAMODB_KEYNAME]
                if 'Log Bucket' in item and item['Log Bucket']:
                    try:
                        keylist = retrieve_all_keys(jobid, item['Log Bucket'])
                    except Exception as e:
                        if 'NoSuchBucket' in str(e):
                            if verbose:
                                logger.info("log bucket %s missing... skip job %s" % (item['Log Bucket'], jobid))
                            continue
                    if verbose:
                        logger.info("deleting %d job files for job %s" % (len(keylist), jobid))
                    delete_keys(keylist, item['Log Bucket'])
                else:
                    if verbose:
                        logger.info("log bucket info missing.. skip job %s" % jobid)
            dd_utils.delete_items(DYNAMODB_TABLE, DYNAMODB_KEYNAME, item_list, verbose=verbose)
        if verbose:
            logger.info("Finished cleaning")

    def create_ami(self, build_from_scratch=True, source_image_to_copy_from=None, source_image_region=None,
                   ubuntu_base_image=None, make_public=False):
        args = dict()
        if build_from_scratch:
            # build from ubuntu 20.04 image and user data
            if ubuntu_base_image:
                args.update({'base_ami': ubuntu_base_image})
        else:
            # copy an existing image
            args.update({'userdata_file': ''})
            if source_image_to_copy_from:
                args.update({'base_ami': source_image_to_copy_from})
            if source_image_region:
                args.update({'base_region': source_image_region})

        return AMI(**args).create_ami_for_tibanna(make_public=make_public)

