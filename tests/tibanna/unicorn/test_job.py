from tibanna.job import Job, Jobs
from tibanna.utils import create_jobid
from tibanna import dd_utils
from tibanna.vars import DYNAMODB_TABLE, EXECUTION_ARN
import mock
import boto3
import pytest


@pytest.fixture
def raise_error():
    raise Exception()


def test_stepfunction_exists():
    assert Job.stepfunction_exists('haha') is False


def test_stepfunction_exists2():
    """this test will fail is there is no step function deployed on aws"""
    sf = boto3.client('stepfunctions')
    res= sf.list_state_machines()
    sfn_name = res['stateMachines'][0]['name']  # some existing step function
    assert Job.stepfunction_exists(sfn_name) is True


def test_job_check_output():
    job = Job(job_id='jid1')
    job._exec_desc = {'output': '{"somefield": "someoutput"}'}
    with mock.patch('tibanna.job.Job.check_status', return_value='SUCCEEDED'):
        res = job.check_output()
    assert res == {'somefield': 'someoutput'}


def test_jobs_status_completed():
    with mock.patch('tibanna.job.Job.check_status', return_value='SUCCEEDED'):
        res = Jobs.status(job_ids=['jid1', 'jid2', 'jid3'])
    assert len(res) == 3
    assert res['completed_jobs'] == ['jid1', 'jid2', 'jid3']
    assert res['running_jobs'] == []
    assert res['failed_jobs'] == []


def test_jobs_status_running():
    with mock.patch('tibanna.job.Job.check_status', return_value='RUNNING'):
        res = Jobs.status(job_ids=['jid1', 'jid2', 'jid3'])
    assert len(res) == 3
    assert res['running_jobs'] == ['jid1', 'jid2', 'jid3']
    assert res['failed_jobs'] == []
    assert res['completed_jobs'] == []


def test_jobs_status_failed():
    with mock.patch('tibanna.job.Job.check_status', return_value='FAILED'):
        res = Jobs.status(job_ids=['jid1', 'jid2', 'jid3'])
    assert len(res) == 3
    assert res['running_jobs'] == []
    assert res['failed_jobs'] == ['jid1', 'jid2', 'jid3']
    assert res['completed_jobs'] == []


def test_jobs_status_failed_exec_arn():
    with mock.patch('tibanna.job.Job.check_status', return_value='FAILED'):
        res = Jobs.status(exec_arns=['ex1', 'ex2', 'ex3'])
    assert len(res) == 3
    assert res['running_jobs'] == []
    assert res['failed_jobs'] == ['ex1', 'ex2', 'ex3']
    assert res['completed_jobs'] == []


def test_describe_exec():
    exec_desc = {'vanilla': 'cinnamon'}
    with mock.patch('botocore.client.BaseClient._make_api_call', return_value=exec_desc):
        res = Job.describe_exec('some_execarn')
    assert res == exec_desc


def test_get_exec_arn_from_job_id():
    jobid = 'test-' + create_jobid()
    exec_name = 'test_execution_name'
    sfn = 'tibanna_unicorn_test'
    exec_arn = EXECUTION_ARN(exec_name, sfn)
    logbucket = 'somebucket'

    # add a job to dynamoDB (dd) before test
    Job.add_to_dd(jobid, exec_name, sfn, logbucket)

    # get exec_arn using get_exec_arn_from_job_id
    res = Job.get_exec_arn_from_job_id(jobid)

    # clean up first
    dd_utils.delete_items(DYNAMODB_TABLE, 'Job Id', [{'Job Id': jobid}])

    # check
    assert res == exec_arn


def test_add_to_dd_and_info():
    jobid = 'test-' + create_jobid()
    execution_name = 'test_execution_name'
    sfn = 'tibanna_unicorn_test'
    logbucket = 'somebucket'

    # add a job to dynamoDB (dd) before test
    Job.add_to_dd(jobid, execution_name, sfn, logbucket)

    # get info from dd
    info = Job.info(job_id=jobid)
    print(info)

    # clean up first
    dd_utils.delete_items(DYNAMODB_TABLE, 'Job Id', [{'Job Id': jobid}])

    # check
    assert info['Step Function'] == sfn
    assert info['Execution Name'] == execution_name
    assert info['Job Id'] == jobid
    assert info['Log Bucket'] == logbucket
    assert 'Time Stamp' in info


def test_exec_arn():
    assert Job(exec_arn='somearn').exec_arn == 'somearn'
    with mock.patch('tibanna.job.Job.get_exec_arn_from_job_id', return_value='somearn'):
        assert Job(job_id='somejobid').exec_arn == 'somearn'


def test_job_id():
    assert Job(job_id='somejobid').job_id == 'somejobid'
    with mock.patch('tibanna.job.Job.get_job_id_from_exec_arn', return_value='somejobid'):
        assert Job(exec_arn='somearn').job_id == 'somejobid'


def test_log_bucket():
    job = Job(job_id='somejobid')
    job._log_bucket = 'somebucket'
    assert job.log_bucket == 'somebucket'


def test_log_bucket_from_dd():
    job = Job(job_id='somejobid')
    with mock.patch('tibanna.job.Job.get_log_bucket_from_job_id', return_value='somebucket'):
        assert job.log_bucket == 'somebucket'


def test_log_bucket_dd2():
    job = Job(job_id='somejobid')
    with mock.patch('tibanna.job.Job.info', return_value={'Log Bucket': 'somebucket'}):
        assert job.log_bucket == 'somebucket'


def test_log_bucket_no_dd():
    job = Job(job_id='somejobid')
    job.sfn = 'somesfn'
    with mock.patch('tibanna.job.Job.info', return_value={}):
        with mock.patch('tibanna.job.Job.get_log_bucket_from_job_id_and_sfn_wo_dd', return_value='somebucket'):
            assert job.log_bucket == 'somebucket'


def test_get_log_bucket_from_job_id():
    with mock.patch('tibanna.job.Job.info', return_value={'job_id': 'somejobid', 'Log Bucket': 'somelogbucket'}):
        assert Job.get_log_bucket_from_job_id(job_id='somejobid') == 'somelogbucket'
