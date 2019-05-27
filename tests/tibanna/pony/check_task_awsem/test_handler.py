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


@valid_env
@pytest.mark.webtest
def test_check_task_awsem_fails_if_job_error_found(check_task_input, s3):
    jobid = 'hahaha'
    check_task_input_modified = check_task_input
    check_task_input_modified['jobid'] = jobid
    job_started = "%s.job_started" % jobid
    s3.put_object(Body=b'', Key=job_started)
    job_error = "%s.error" % jobid
    s3.put_object(Body=b'', Key=job_error)
    res = service.handler(check_task_input_modified, '')
    assert ('error' in res)
    s3.delete_objects(Delete={'Objects': [{'Key': job_started}]})
    s3.delete_objects(Delete={'Objects': [{'Key': job_error}]})
