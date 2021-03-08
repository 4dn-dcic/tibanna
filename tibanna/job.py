import boto3
from datetime import datetime
from . import create_logger
from tibanna import dd_utils
from .vars import (
    EXECUTION_ARN,
    AWS_REGION,
    DYNAMODB_TABLE
)


# logger
logger = create_logger(__name__)


class Jobs(object):

    @staticmethod
    def status(job_ids=None, exec_arns=None):
        res = dict()
        statuses = dict()
        if job_ids: 
            for j in job_ids:
                statuses.update({j: Job(job_id=j).check_status()})
        if exec_arns:
            for arn in exec_arns:
                statuses.append({arn: Job(exec_arn=arn).check_status()})
        res['completed_jobs'] = [job for job, status in iter(statuses.items()) if status == 'SUCCEEDED']
        res['failed_jobs'] = [job for job, status in iter(statuses.items()) if status == 'FAILED']
        res['running_jobs'] = [job for job, status in iter(statuses.items()) if status == 'RUNNING']
        return res


class Job(object):

    def __init__(self, job_id=None, exec_arn=None, sfn=None):
        if not job_id and not exec_arn:
            raise Exception("Provide either through job id or execution arn to retrieve a job.")
        self.job_id = job_id
        self.exec_arn = exec_arn
        self.sfn = sfn  # only for old tibanna
        self.exec_desc = None
        self.log_bucket = None

    def check_status(self):
        '''checking status of an execution.
        It works only if the execution info is still in the step function.'''
        self.update_exec_desc()
        return self.exec_desc['status']

    def check_output(self):
        '''checking status of an execution first and if it's success, get output.
        It works only if the execution info is still in the step function.'''
        if self.check_status() == 'SUCCEEDED':
            self.update_exec_desc()
            if 'output' in self.desc:
                return json.loads(self.desc['output'])
            else:
                return None

    def update_exec_desc(self):
        """sfn is needed only for old tibanna
        """
        if not self.exec_desc:
            self.update_exec_arn_from_job_id()
            self.exec_desc = self.describe_exec(self.exec_arn)

    def update_exec_arn_from_job_id(self):
        if self.job_id and not self.exec_arn:
            try:
                self.exec_arn = self.get_exec_arn_from_job_id(self.job_id)
            except Exception as e:
                if sfn:
                    self.exec_arn = self.get_exec_arn_from_job_id_and_sfn_wo_dd(self.job_id, sfn=self.sfn)

    @classmethod
    def get_exec_arn_from_job_id(cls, job_id):
        ddinfo = cls.info(job_id)
        if not ddinfo:
            raise Exception("Can't find exec_arn from the job_id")
        exec_name = ddinfo.get('Execution Name', '')
        sfn = ddinfo.get('Step Function', '')
        exec_arn = EXECUTION_ARN(exec_name, sfn)
        if not exec_arn:
            raise Exception("Can't find exec_arn from the job_id")
        return exec_arn

    @staticmethod
    def get_exec_arn_from_job_id_and_sfn_wo_dd(job_id, sfn):
        """This is for old tibanna that did not use dyndmoDB.
        We're keeping it just for backward compatibility.
        Basically searching through all executions in a given sfn to
        find the execution that matches the job ID.
        Very slow.
        """
        stateMachineArn = STEP_FUNCTION_ARN(sfn)
        try:
            sf = boto3.client("stepfuntions", region_name=AWS_REGION)
            res = sf.list_executions(stateMachineArn=stateMachineArn)
            while True:
                if 'executions' not in res or not res['executions']:
                    break
                breakwhile = False
                for exc in res['executions']:
                    desc = sf.describe_execution(executionArn=exc['executionArn'])
                    if job_id == str(json.loads(desc['input'])['jobid']):
                        return exc['executionArn']
                if 'nextToken' in res:
                    res = sf.list_executions(nextToken=res['nextToken'],
                                             stateMachineArn=stateMachineArn)
                else:
                    break
        except:
            raise Exception("Cannot retrieve job. Try again later.")

    @classmethod
    def info(cls, job_id):
        '''returns content from dynamodb for a given job id in a dictionary form'''
        ddres = cls.get_dd(job_id)
        return cls.get_info_from_dd(ddres)

    @staticmethod
    def describe_exec(exec_arn):
        sts = boto3.client('stepfunctions', region_name=AWS_REGION)
        return sts.describe_execution(executionArn=exec_arn)

    @staticmethod
    def get_dd(job_id):
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

    @staticmethod
    def get_info_from_dd(ddres):
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

    @staticmethod
    def add_to_dd(job_id, execution_name, sfn, logbucket, verbose=True):
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
                        'S': job_id
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

