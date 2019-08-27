from tibanna.lambdas import check_task_awsem as service
from tibanna.exceptions import (
    EC2StartingException,
    StillRunningException,
    MetricRetrievalException
)
import pytest
import boto3
import random
import string
import json
from datetime import datetime

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
    job_started = "%s.job_started" % jobid
    s3.delete_objects(Delete={'Objects': [{'Key': job_started}]})
    with pytest.raises(EC2StartingException) as excinfo:
        service.handler(check_task_input_modified, '')

    assert 'Failed to find jobid' in str(excinfo.value)


@pytest.mark.webtest
def test_check_task_awsem_throws_exception_if_not_done(check_task_input):
    with pytest.raises(StillRunningException) as excinfo:
        service.handler(check_task_input, '')

    assert 'still running' in str(excinfo.value)
    assert 'error' not in check_task_input


@pytest.mark.webtest
def test_check_task_awsem(check_task_input, s3):
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
    with pytest.raises(MetricException) as excinfo:
        retval = service.handler(check_task_input_modified, '')
    assert 'error getting metrics' in str(excinfo)
    s3.delete_objects(Delete={'Objects': [{'Key': job_started}]})
    s3.delete_objects(Delete={'Objects': [{'Key': job_success}]})
    s3.delete_objects(Delete={'Objects': [{'Key': postrunjson}]})
    assert 'postrunjson' in retval
    assert retval['postrunjson'] == jsondict
    del retval['postrunjson']
    assert retval == check_task_input_modified


@pytest.mark.webtest
def test_check_task_awsem_with_long_postrunjson(check_task_input, s3):
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
    with pytest.raises(MetricException) as excinfo:
        retval = service.handler(check_task_input_modified, '')
    assert 'error getting metrics' in str(excinfo)
    s3.delete_objects(Delete={'Objects': [{'Key': job_started}]})
    s3.delete_objects(Delete={'Objects': [{'Key': job_success}]})
    s3.delete_objects(Delete={'Objects': [{'Key': postrunjson}]})
    assert 'postrunjson' in retval
    assert 'Job' in retval['postrunjson']
    assert 'Output' in retval['postrunjson']['Job']
    assert 'log' in retval['postrunjson']
    assert retval['postrunjson']['log'] == "postrun json not included due to data size limit"
    del retval['postrunjson']
    assert retval == check_task_input_modified
