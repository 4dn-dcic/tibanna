from tibanna.lambdas import check_task_awsem as service
from tibanna.exceptions import (
    EC2StartingException,
    StillRunningException,
    EC2IdleException,
    JobAbortedException
)
import pytest
import boto3
import random
import string
import json
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from tibanna.vars import AWSEM_TIME_STAMP_FORMAT


def _mock_ec2_client_only(mocker):
    """Mock only the EC2 client (terminate_instances) so these tests don't
    attempt a live EC2 mutation against a made-up/empty instance id, while
    leaving the real S3 client (used elsewhere in the same process) alone.
    """
    real_boto3_client = boto3.client

    def fake_client(service_name, *args, **kwargs):
        if service_name == 'ec2':
            return MagicMock()
        return real_boto3_client(service_name, *args, **kwargs)

    return mocker.patch('tibanna.check_task.boto3.client', side_effect=fake_client)


@pytest.fixture()
def check_task_input():
    return {"config": {"log_bucket": "tibanna-output"},
            "jobid": "test_job",
            "push_error_to_end": True
            }


@pytest.fixture()
def s3(check_task_input):
    bucket_name = check_task_input['config']['log_bucket']
    return boto3.resource('s3').Bucket(bucket_name)


@pytest.mark.webtest
def test_check_task_awsem_fails_if_no_job_started(check_task_input, s3):
    # ensure there is no job started
    jobid = 'notmyjobid'
    check_task_input_modified = check_task_input
    check_task_input_modified['jobid'] = jobid
    check_task_input_modified['config']['start_time'] = datetime.strftime(datetime.now(tzutc()) - timedelta(minutes=4),
                                                                          AWSEM_TIME_STAMP_FORMAT)
    job_started = "%s.job_started" % jobid
    s3.delete_objects(Delete={'Objects': [{'Key': job_started}]})
    with pytest.raises(EC2StartingException) as excinfo:
        service.handler(check_task_input_modified, '')
    assert 'Failed to find jobid' in str(excinfo.value)


@pytest.mark.webtest
def test_check_task_awsem_fails_if_no_job_started_for_too_long(check_task_input, s3):
    # ensure there is no job started
    jobid = 'notmyjobid'
    check_task_input_modified = check_task_input
    check_task_input_modified['jobid'] = jobid
    check_task_input_modified['config']['start_time'] = datetime.strftime(datetime.now(tzutc()) - timedelta(minutes=13),
                                                                          AWSEM_TIME_STAMP_FORMAT)
    job_started = "%s.job_started" % jobid
    s3.delete_objects(Delete={'Objects': [{'Key': job_started}]})
    with pytest.raises(EC2IdleException) as excinfo:
        service.handler(check_task_input_modified, '')
    assert 'Failed to find jobid' in str(excinfo.value)


def test_check_task_awsem_aborted(check_task_input, s3):
    jobid = 'lalala'
    check_task_input_modified = check_task_input
    check_task_input_modified['jobid'] = jobid
    job_started = "%s.job_started" % jobid
    job_aborted = "%s.aborted" % jobid
    s3.put_object(Body=b'', Key=job_started)
    s3.put_object(Body=b'', Key=job_aborted)
    with pytest.raises(JobAbortedException) as excinfo:
        service.handler(check_task_input, '')
    assert 'aborted' in str(excinfo.value)
    # cleanup
    s3.delete_objects(Delete={'Objects': [{'Key': job_started}]})
    s3.delete_objects(Delete={'Objects': [{'Key': job_aborted}]})


@pytest.mark.webtest
def test_check_task_awsem_throws_exception_if_not_done(check_task_input):
    with pytest.raises(StillRunningException) as excinfo:
        service.handler(check_task_input, '')
    assert 'still running' in str(excinfo.value)
    assert 'error' not in check_task_input


@pytest.mark.webtest
def test_check_task_awsem(check_task_input, s3, mocker):
    """D3 regression (webtest): a valid .success marker plus valid postrun
    data must complete successfully even when metrics retrieval fails (here,
    because the job's tiny/synthetic start_time makes CloudWatch retrieval
    fail) - the failure is recorded as a structured Metrics_status/error
    instead of aborting the job as failed.
    """
    _mock_ec2_client_only(mocker)
    jobid = 'lalala'
    check_task_input_modified = check_task_input
    check_task_input_modified['jobid'] = jobid
    job_started = "%s.job_started" % jobid
    s3.put_object(Body=b'', Key=job_started)
    job_success = "%s.success" % jobid
    s3.put_object(Body=b'', Key=job_success)
    postrunjson = "%s.postrun.json" % jobid
    jsondict = {"config": {"log_bucket": "somelogbucket"},
                "Job": {"JOBID": jobid, "start_time": '20190814-21:01:07-UTC',
                        "App": {}, "Output": {},
                        "Input": {'Input_files_data': {}, 'Input_parameters': {}, 'Secondary_files_data': {}}}}
    jsoncontent = json.dumps(jsondict)
    s3.put_object(Body=jsoncontent.encode(), Key=postrunjson)
    retval = service.handler(check_task_input_modified, '')
    assert 'postrunjson' in retval
    assert retval['postrunjson']['Job']['Metrics_status'] in ('ok', 'failed')
    s3.delete_objects(Delete={'Objects': [{'Key': job_started}]})
    s3.delete_objects(Delete={'Objects': [{'Key': job_success}]})
    s3.delete_objects(Delete={'Objects': [{'Key': postrunjson}]})


@pytest.mark.webtest
def test_check_task_awsem_with_long_postrunjson(check_task_input, s3, mocker):
    """D3 regression (webtest): same as test_check_task_awsem, but with an
    oversized `commands` field that triggers the postrun-json truncation
    path - completion must still succeed despite the metrics failure.
    """
    _mock_ec2_client_only(mocker)
    jobid = 'some_uniq_jobid'
    check_task_input_modified = check_task_input
    check_task_input_modified['jobid'] = jobid
    job_started = "%s.job_started" % jobid
    s3.put_object(Body=b'', Key=job_started)
    job_success = "%s.success" % jobid
    s3.put_object(Body=b'', Key=job_success)
    postrunjson = "%s.postrun.json" % jobid
    verylongstring = ''.join(random.choice(string.ascii_uppercase) for _ in range(50000))
    jsondict = {"config": {"log_bucket": "somelogbucket"},
                "Job": {"JOBID": jobid, "start_time": '20190814-21:01:07-UTC',
                        "App": {}, "Output": {},
                        "Input": {'Input_files_data': {}, 'Input_parameters': {}, 'Secondary_files_data': {}}},
                "commands": verylongstring}
    jsoncontent = json.dumps(jsondict)
    s3.put_object(Body=jsoncontent.encode(), Key=postrunjson)
    retval = service.handler(check_task_input_modified, '')
    assert 'postrunjson' in retval
    assert 'Job' in retval['postrunjson']
    assert retval['postrunjson']['Job']['Metrics_status'] in ('ok', 'failed')
    s3.delete_objects(Delete={'Objects': [{'Key': job_started}]})
    s3.delete_objects(Delete={'Objects': [{'Key': job_success}]})
    s3.delete_objects(Delete={'Objects': [{'Key': postrunjson}]})
