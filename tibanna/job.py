import boto3
import json
from datetime import datetime
from . import create_logger
from tibanna import dd_utils
from .vars import (
    STEP_FUNCTION_ARN,
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
                statuses.update({arn: Job(exec_arn=arn).check_status()})
        res['completed_jobs'] = [job for job, status in iter(statuses.items()) if status == 'SUCCEEDED']
        res['failed_jobs'] = [job for job, status in iter(statuses.items()) if status == 'FAILED']
        res['running_jobs'] = [job for job, status in iter(statuses.items()) if status == 'RUNNING']
        return res


class Job(object):

    def __init__(self, job_id=None, exec_arn=None, sfn=None):
        """A job can be identified with either a job_id or an exec_arn.
        For old tibanna versions (with no dynamoDB deployed),
        a job can be identified with a job_id and sfn.
        """
        if not job_id and not exec_arn:
            raise Exception("Provide either through job id or execution arn to retrieve a job.")
        self._job_id = job_id
        self._exec_arn = exec_arn
        self.sfn = sfn  # only for old tibanna
        self._exec_desc = None
        self._log_bucket = None
        self.costupdater_exec_arn = None
        self.costupdater_exec_desc = None

        # cache for boto3 client for step function
        self._client_sfn = None

    @property
    def client_sfn(self):
        if not self._client_sfn:
            self._client_sfn = boto3.client('sfn', region=AWS_REGION)
        return self._client_sfn

    def check_costupdater_status(self):
        self.update_costupdater_exec_desc()
        return self.costupdater_exec_desc['status']

    def check_status(self):
        '''checking status of an execution.
        It works only if the execution info is still in the step function.'''
        return self.exec_desc['status']

    def check_output(self):
        '''checking status of an execution first and if it's success, get output.
        It works only if the execution info is still in the step function.'''
        if self.check_status() == 'SUCCEEDED':
            if 'output' in self.exec_desc:
                return json.loads(self.exec_desc['output'])
            else:
                return None

    @property
    def exec_arn(self):
        if self._exec_arn:
            return self._exec_arn
        elif self.job_id:  # figure out exec_arn frmo job_id
            try:
                self._exec_arn = self.get_exec_arn_from_job_id(self.job_id)
            except Exception as e:
                if self.sfn:
                    self._exec_arn = self.get_exec_arn_from_job_id_and_sfn_wo_dd(self.job_id, sfn=self.sfn)
                else:
                    raise e
            return self._exec_arn

    @property
    def exec_desc(self):
        """sfn is needed only for old tibanna
        """
        if not self._exec_desc:
            self._exec_desc = self.describe_exec(self.exec_arn)
        return self._exec_desc

    @property
    def job_id(self):
        if not self._job_id:
            if self.exec_arn:
                self._job_id = self.get_job_id_from_exec_arn(self.exec_arn)
            else:
                raise("Can't find job_id - either provide job_id or exec_arn")
        return self._job_id

    @property
    def log_bucket(self):
        if not self._log_bucket:
            if self.job_id:
                try:
                    # first try dynanmodb to get logbucket
                    self._log_bucket = self.get_log_bucket_from_job_id(self.job_id)
                except Exception as e:
                    logger.warning(f'Unable to retrieve metadata from dynamo: {str(e)}')
                    if self.sfn:
                        self._log_bucket = self.get_log_bucket_from_job_id_and_sfn_wo_dd(self.job_id, self.sfn)
            if not self._log_bucket:
                raise Exception("Cannot retrieve log bucket.")
        return self._log_bucket

    @classmethod
    def get_log_bucket_from_job_id(cls, job_id):
        return cls.info(job_id)['Log Bucket']

    @staticmethod
    def get_log_bucket_from_job_id_and_sfn_wo_dd(job_id, sfn):
        stateMachineArn = STEP_FUNCTION_ARN(sfn)
        sf = boto3.client('stepfunctions')
        logbucket = None  # should be resolved below
        logger.warning(f'Could not get job metadata from DynamoDB - falling back to sfn {stateMachineArn}')
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
        if logbucket:
            return logbucket
        else:
            raise Exception("Cannot retrieve log bucket.")

    @staticmethod
    def get_job_id_from_exec_arn(exec_arn):
        sf = boto3.client('stepfunctions')
        desc = sf.describe_execution(executionArn=exec_arn)
        return str(json.loads(desc['input'])['jobid'])

    def update_costupdater_exec_desc(self):
        if not self.costupdater_exec_desc:
            self.update_costupdater_exec_arn_from_job_id()
            self.costupdater_exec_desc = self.describe_exec(self.costupdater_exec_arn)

    def update_costupdater_exec_arn_from_job_id(self):
        if not self.costupdater_exec_arn:
            self.costupdater_exec_arn = self.get_costupdater_exec_arn_from_job_id(self.job_id)
        # older tibanna does not have cost updater so we don't need to try the old way of doing it without dd.

    @staticmethod
    def stepfunction_exists(sfn_name):
        sf = boto3.client('stepfunctions')
        try:
            sf.describe_state_machine(stateMachineArn=STEP_FUNCTION_ARN(sfn_name))
            return True
        except Exception as e:
            if "State Machine Does Not Exist" in str(e):
                return False

    @classmethod
    def get_costupdater_exec_arn_from_job_id(cls, job_id):
        ddinfo = cls.info(job_id)
        if not ddinfo:
            raise Exception("Can't find dynamoDB entry for job_id %s" % job_id)
        exec_name = ddinfo.get('Execution Name', '')
        if not exec_name:
            raise Exception("Can't find exec_name from dynamoDB for job_id %s" % job_id)
        sfn = ddinfo.get('Step Function', '')
        if not cls.stepfunction_exists(sfn + "_costupdater"):
            raise Exception("Costupdater step function does not exist." +
                            "To use costupdater, upgrade your tibanna to >=1.1 and redeploy with -C option!")
        exec_arn = EXECUTION_ARN(exec_name, sfn + "_costupdater")
        return exec_arn

    @classmethod
    def get_exec_arn_from_job_id(cls, job_id):
        ddinfo = cls.info(job_id)
        if not ddinfo:
            raise Exception("Can't find dynamoDB entry for job_id %s" % job_id)
        exec_name = ddinfo.get('Execution Name', '')
        if not exec_name:
            raise Exception("Can't find exec_name from dynamoDB for job_id %s" % job_id)
        sfn = ddinfo.get('Step Function', '')
        exec_arn = EXECUTION_ARN(exec_name, sfn)
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
        '''returns content from dynamodb for a given job id in a dictionary form.
        returns None if the entry does not exist in dynamoDB'''
        ddres = cls.get_dd(job_id)
        return cls.get_info_from_dd(ddres)

    @staticmethod
    def describe_exec(exec_arn):
        sf = boto3.client('stepfunctions', region_name=AWS_REGION)
        return sf.describe_execution(executionArn=exec_arn)

    @staticmethod
    def get_dd(job_id):
        '''return raw content from dynamodb for a given job id'''
        for _ in range(3):  # retry this just in case
            try:
                dd = boto3.client('dynamodb')
                ddres = dd.query(TableName=DYNAMODB_TABLE,
                                 KeyConditions={'Job Id': {'AttributeValueList': [{'S': job_id}],
                                                           'ComparisonOperator': 'EQ'}})
                return ddres
            except Exception as e:
                logger.error("DynamoDB entry not found: %s" % e)
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
            dydb.describe_table(TableName=DYNAMODB_TABLE)
        except Exception as e:
            logger.error("Not adding to dynamo table: %s" % e)
            return
        for _ in range(5):  # try to add to dynamo 5 times
            try:
                item ={
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
                if verbose:
                    logger.info("Trying to add the following item to dynamoDB: " + str(item))

                response = dydb.put_item(
                    TableName=DYNAMODB_TABLE,
                    Item=item,
                    ReturnConsumedCapacity='TOTAL'
                )
                if 'CapacityUnits' in response['ConsumedCapacity']:
                    if verbose:
                        logger.warning("Successfully put item to dynamoDB: " + str(response))
                    break
                else:
                    logger.error(f"Encountered an unknown error inserting into dynamo: {response}")
            except Exception as e:
                logger.error(f"Encountered exception inserting into dynamoDB: {e}")

