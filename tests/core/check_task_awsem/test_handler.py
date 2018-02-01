from core.check_task_awsf import service
from ..conftest import valid_env
import pytest
from core import utils
from core.utils import AWSEMJobErrorException


@pytest.fixture(scope='session')
def check_task_input():
    return {"config": {"log_bucket": "tibanna-output"},
            "jobid": "test_job"
            }


@pytest.fixture(scope='session')
def s3(check_task_input):
    bucket_name = check_task_input['config']['log_bucket']
    return utils.s3Utils(bucket_name, bucket_name, bucket_name)


@pytest.fixture()
def job_started(check_task_input, s3):
    jobid = check_task_input['jobid']
    job_started_name = "%s.job_started" % jobid
    s3.s3_put('', job_started_name)
    return job_started_name


@valid_env
@pytest.mark.webtest
def test_check_task_awsf_fails_if_no_job_started(check_task_input, s3):
    # ensure there is no job started
    jobid = check_task_input['jobid']
    job_started = "%s.job_started" % jobid
    s3.delete_key(job_started)

    with pytest.raises(service.EC2StartingException) as excinfo:
        service.handler(check_task_input, '')

    assert 'Failed to find jobid' in str(excinfo.value)


@valid_env
@pytest.mark.webtest
def test_check_task_awsf_fails_if_job_error_found(check_task_input, s3, job_started):
    jobid = check_task_input['jobid']
    job_error = "%s.error" % jobid
    s3.s3_put('', job_error)

    with pytest.raises(AWSEMJobErrorException) as excinfo:
        service.handler(check_task_input, '')

    s3.delete_key(job_error)
    assert 'Job encountered an error' in str(excinfo.value)


@valid_env
@pytest.mark.webtest
def test_check_task_awsf_throws_exception_if_not_done(check_task_input, s3, job_started):

    with pytest.raises(service.StillRunningException) as excinfo:
        service.handler(check_task_input, '')

    assert 'still running' in str(excinfo.value)


@valid_env
@pytest.mark.webtest
def test_check_task_awsf(check_task_input, s3, job_started):
    jobid = check_task_input['jobid']
    job_success = "%s.success" % jobid
    s3.s3_put('', job_success)
    postrunjson = "%s.postrun.json" % jobid
    s3.s3_put('{"test":"test"}', postrunjson)

    retval = service.handler(check_task_input, '')
    s3.delete_key(job_success)
    s3.delete_key(postrunjson)
    assert 'postrunjson' in retval
    assert retval['postrunjson'] == {"test": "test"}
    del retval['postrunjson']
    assert retval == check_task_input
