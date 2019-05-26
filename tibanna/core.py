import os
import boto3
import json
import time
import copy
import logging
from datetime import datetime
from uuid import uuid4, UUID
from tibanna.vars.Vars import (
    _tibanna,
    AWS_REGION,
    TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
    DYNAMODB_TABLE,
    STEP_FUNCTION_ARN,
    EXECUTION_ARN,
)
from tibanna.utils import (
    _tibanna_settings,
    printlog,
    create_jobid
)


# logger
LOG = logging.getLogger(__name__)


class Run(object):

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

    def run_workflow(self, input_json, accession='', sfn='tibanna_pony',
                     env='fourfront-webdev', jobid=None, sleep=3):
        '''
        accession is unique name that we be part of run id
        '''
        client = boto3.client('stepfunctions', region_name='us-east-1')
        base_url = 'https://console.aws.amazon.com/states/home?region=us-east-1#/executions/details/'
        input_json_copy = copy.deepcopy(input_json)
        # build from appropriate input json
        # assume run_type and and run_id
        if 'run_name' in input_json_copy['config']:
            if _tibanna not in input_json_copy:
                input_json_copy[_tibanna] = dict()
            input_json_copy[_tibanna]['run_name'] = input_json_copy['config']['run_name']
        input_json_copy = _tibanna_settings(input_json_copy, force_inplace=True, env=env)
        run_name = self.randomize_run_name(input_json_copy[_tibanna]['run_name'], sfn)
        input_json_copy[_tibanna]['run_name'] = run_name
        input_json_copy['config']['run_name'] = run_name
        # updated arn
        arn = EXECUTION_ARN(run_name, sfn)
        input_json_copy[_tibanna]['exec_arn'] = arn
        # calculate what the url will be
        url = "%s%s" % (base_url, arn)
        input_json_copy[_tibanna]['url'] = url
        # add jobid
        if not jobid:
            jobid = create_jobid()
        input_json_copy['jobid'] = jobid
        aws_input = json.dumps(input_json_copy)
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
        self.add_to_dydb(jobid, run_name, sfn, input_json_copy['config']['log_bucket'])
        # print some info
        print("response from aws was: \n %s" % response)
        print("url to view status:")
        print(input_json_copy[_tibanna]['url'])
        input_json_copy[_tibanna]['response'] = response
        return input_json_copy

    def add_to_dydb(self, awsem_job_id, execution_name, sfn, logbucket):
        dydb = boto3.client('dynamodb')
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

    def kill_all(self, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME):
        """killing all the running jobs"""
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

    def log(self, exec_arn=None, job_id=None, exec_name=None,
            sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, postrunjson=False):
        if postrunjson:
            suffix = '.postrun.json'
        else:
            suffix = '.log'
        sf = boto3.client('stepfunctions')
        if not exec_arn and exec_name:
            exec_arn = EXECUTION_ARN(exec_name, sfn)
        if exec_arn:
            desc = sf.describe_execution(executionArn=exec_arn)
            jobid = str(json.loads(desc['input'])['jobid'])
            logbucket = str(json.loads(desc['input'])['config']['log_bucket'])
            res_s3 = boto3.client('s3').get_object(Bucket=logbucket, Key=jobid + suffix)
            if res_s3:
                return(res_s3['Body'].read())
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
                            return(res_s3['Body'].read())
                        break
                if 'nextToken' in res:
                    res = sf.list_executions(nextToken=res['nextToken'],
                                             stateMachineArn=stateMachineArn)
                else:
                    break
        return None

    def stat(self, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, status=None, verbose=False):
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

    def list_sfns(self, numbers=False, sfn_type="unicorn"):
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

    def prep_input_json_template(self, filename, webprod=False, tag=None):
        Tibanna_dir = os.path.dirname(os.path.realpath(__file__)).replace('/tibanna', '')
        template = Tibanna_dir + '/test_json/' + filename
        with open(template, 'r') as f:
            input_json_template = json.load(f)
        # webdev ->webprod
        if webprod:
            input_json_template['output_bucket'] = 'elasticbeanstalk-fourfront-webprod-wfoutput'
            input_json_template['_tibanna']['env'] = 'fourfront-webprod'
            for inb in input_json_template['input_files']:
                inb['bucket_name'] = inb['bucket_name'].replace('webdev', 'webprod')
        if tag:
            input_json_template['tag'] = tag
            self.clear_input_json_template(input_json_template)
        return input_json_template

    def clear_input_json_template(self, input_json_template):
        """clear awsem template for reuse"""
        if 'response' in input_json_template['_tibanna']:
            del(input_json_template['_tibanna']['response'])
        if 'run_name' in input_json_template['_tibanna'] and len(input_json_template['_tibanna']['run_name']) > 40:
            input_json_template['_tibanna']['run_name'] = input_json_template['_tibanna']['run_name'][:-36]
            input_json_template['config']['run_name'] = input_json_template['_tibanna']['run_name']

    def rerun(self, exec_arn, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME,
              override_config=None, app_name_filter=None, name=None):
        """rerun a specific job
        override_config : dictionary for overriding config (keys are the keys inside config)
            e.g. override_config = { 'instance_type': 't2.micro' }
        app_name_filter : app_name (e.g. hi-c-processing-pairs), if specified,
        then rerun only if it matches app_name
        """
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
        if override_config:
            for k, v in iter(override_config.items()):
                input_json_template['config'][k] = v
        return(self.run_workflow(input_json_template, sfn=sfn))

    def rerun_many(self, sfn=TIBANNA_DEFAULT_STEP_FUNCTION_NAME, stopdate='13Feb2018', stophour=13,
                   stopminute=0, offset=0, sleeptime=5, status='FAILED',
                   override_config=None, app_name_filter=None):
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
                           override_config=override_config, app_name_filter=app_name_filter)
                time.sleep(sleeptime)
