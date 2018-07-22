from core.check_task_awsem import service
from ..conftest import valid_env
import pytest
from dcicutils import s3_utils
import random
import string
import logging

LOG = logging.getLogger(__name__)


@pytest.fixture()
def check_task_input():
    return {"config": {"log_bucket": "tibanna-output"},
            "jobid": "test_job",
            "push_error_to_end": True
            }


@pytest.fixture()
def s3(check_task_input):
    bucket_name = check_task_input['config']['log_bucket']
    return s3_utils.s3Utils(bucket_name, bucket_name, bucket_name)


@pytest.fixture()
def job_started(check_task_input, s3):
    jobid = check_task_input['jobid']
    job_started_name = "%s.job_started" % jobid
    s3.s3_put('', job_started_name)
    return job_started_name


@valid_env
@pytest.mark.webtest
def test_check_task_awsem_fails_if_no_job_started(check_task_input, s3):
    # ensure there is no job started
    jobid = check_task_input['jobid']
    job_started = "%s.job_started" % jobid
    s3.delete_key(job_started)

    with pytest.raises(service.EC2StartingException) as excinfo:
        service.handler(check_task_input, '')

    assert 'Failed to find jobid' in str(excinfo.value)


@valid_env
@pytest.mark.webtest
def test_check_task_awsem_fails_if_job_error_found(check_task_input, s3, job_started):
    jobid = check_task_input['jobid']
    job_error = "%s.error" % jobid
    s3.s3_put('', job_error)

    res = service.handler(check_task_input, '')
    assert ('error' in res)

    s3.delete_key(job_error)


@valid_env
@pytest.mark.webtest
def test_check_task_awsem_throws_exception_if_not_done(check_task_input, s3, job_started):
    with pytest.raises(service.StillRunningException) as excinfo:
        service.handler(check_task_input, '')

    assert 'still running' in str(excinfo.value)
    assert 'error' not in check_task_input


@valid_env
@pytest.mark.webtest
def test_check_task_awsem(check_task_input, s3, job_started):
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


@valid_env
@pytest.mark.webtest
def test_check_task_awsem_with_long_postrunjson(check_task_input, s3, job_started):
    jobid = check_task_input['jobid']
    job_success = "%s.success" % jobid
    s3.s3_put('', job_success)
    postrunjson = "%s.postrun.json" % jobid
    verylongstring = ''.join(random.choice(string.ascii_uppercase) for _ in range(50000))
    s3.s3_put('{"test": "' + verylongstring + '", "Job": {"Output": {}}}', postrunjson)

    retval = service.handler(check_task_input, '')
    s3.delete_key(job_success)
    s3.delete_key(postrunjson)
    assert 'postrunjson' in retval
    assert 'Job' in retval['postrunjson']
    assert 'Output' in retval['postrunjson']['Job']
    assert 'log' in retval['postrunjson']
    assert retval['postrunjson']['log'] == "postrun json not included due to data size limit"
    del retval['postrunjson']
    assert retval == check_task_input
