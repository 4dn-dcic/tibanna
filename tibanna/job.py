import boto3
from .vars import (
    EXECUTION_ARN,
    AWS_REGION,
    DYNAMODB_TABLE
)


class Jobs(object):

    @staticmethod
    def status(job_ids, exec_arns):
        res = dict()
        statuses = dict()
        if job_id: 
            for j in job_ids:
                statuses.update({j: Job(job_id=j).check_status()})
        if exec_arn:
            for arn in exec_arns:
                statuses.append({arn: Job(exec_arn=arn).check_status()})
        res['succeeded_jobs'] = [for job, status in iter(statuses.items()) if status == 'SUCCEEDED']
        res['failed_jobs'] = [for job, status in iter(statuses.items()) if status == 'FAILED']
        res['running_jobs'] = [for job, status in iter(statuses.items()) if status == 'RUNNING']
        return res


class Job(object):

    def __init__(self, job_id=None, exec_arn=None):
        if not job_id and not exec_arn:
            raise Exception("Provide either through job id or execution arn to retrieve a job.")
        self.job_id = job_id
        self.exec_arn = exec_arn
        self.exec_desc = None

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
        if not self.exec_desc:
            self.update_exec_arn_from_job_id()
            self.exec_desc = self.describe_exec(self.exec_arn)

    def update_exec_arn_from_job_id(self):
        if self.job_id and not self.exec_arn:
            self.exec_arn = self.get_exec_arn_from_job_id(self.job_id)

    @classmethod
    def get_exec_arn_from_job_id(cls, job_id):
        ddinfo = cls.info()
        if not ddinfo:
            raise Exception("Can't find exec_arn from the job_id")
        exec_name = ddinfo.get('Execution Name', '')
        sfn = ddinfo.get('Step Function', '')
        exec_arn = EXECUTION_ARN(exec_name, sfn)
        if not exec_arn:
            raise Exception("Can't find exec_arn from the job_id")
        return exec_arn

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
