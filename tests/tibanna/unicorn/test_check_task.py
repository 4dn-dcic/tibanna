import json
from unittest.mock import MagicMock
from tibanna.check_task import CheckTask


def _postrunjson_dict(jobid, instance_id):
    return {
        "config": {"log_bucket": "somelogbucket"},
        "Job": {
            "JOBID": jobid,
            "start_time": '20190814-21:01:07-UTC',
            "App": {},
            "Output": {},
            "Input": {'Input_files_data': {}, 'Input_parameters': {}, 'Secondary_files_data': {}},
            "instance_id": instance_id,
            "filesystem": "/dev/nvme1n1",
        },
    }


def _make_check_task_input(jobid, instance_id, disable_metrics_collection=False):
    return {
        "config": {
            "log_bucket": "somelogbucket",
            "instance_id": instance_id,
            "start_time": "20190814-21:01:07-UTC",
            "disable_metrics_collection": disable_metrics_collection,
        },
        "jobid": jobid,
    }


def _mock_s3_layer(mocker, postrunjson_dict, existing_keys):
    mocker.patch('tibanna.check_task.does_key_exist',
                 side_effect=lambda bucket, key, quiet=False: key in existing_keys)
    mocker.patch('tibanna.check_task.read_s3', return_value=json.dumps(postrunjson_dict))
    mocker.patch('tibanna.check_task.put_object_s3')


def test_success_with_metrics_failure_still_terminates(mocker):
    """D3: a valid .success marker plus valid postrun data must complete
    successfully - and still reach instance termination - even when metrics
    retrieval/plotting fails. The failure is recorded as a structured
    Metrics_status/Metrics_error instead of aborting the job.
    """
    jobid = 'myjob'
    instance_id = 'i-0123456789abcdef0'
    prj_dict = _postrunjson_dict(jobid, instance_id)
    existing_keys = {'%s.job_started' % jobid, '%s.success' % jobid, '%s.postrun.json' % jobid}
    _mock_s3_layer(mocker, prj_dict, existing_keys)

    mock_ec2 = MagicMock()
    mocker.patch('tibanna.check_task.boto3.client', return_value=mock_ec2)

    ct = CheckTask(_make_check_task_input(jobid, instance_id))
    ct.TibannaResource = MagicMock(side_effect=Exception("no cloudwatch data for this instance"))
    ct.API = MagicMock()

    result = ct.run()

    assert 'postrunjson' in result
    assert result['postrunjson']['Job']['Metrics_status'] == 'failed'
    assert 'Metrics_error' in result['postrunjson']['Job']
    mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=[instance_id])


def test_success_with_metrics_ok(mocker):
    """A valid .success marker with metrics succeeding records Metrics_status=ok
    and still terminates."""
    jobid = 'myjob2'
    instance_id = 'i-0123456789abcdef1'
    prj_dict = _postrunjson_dict(jobid, instance_id)
    existing_keys = {'%s.job_started' % jobid, '%s.success' % jobid, '%s.postrun.json' % jobid}
    _mock_s3_layer(mocker, prj_dict, existing_keys)

    mock_ec2 = MagicMock()
    mocker.patch('tibanna.check_task.boto3.client', return_value=mock_ec2)

    ct = CheckTask(_make_check_task_input(jobid, instance_id))
    mock_resources = MagicMock()
    mock_resources.as_dict.return_value = {'max_cpu_utilization_percent': 42}
    ct.TibannaResource = MagicMock(return_value=mock_resources)
    ct.API = MagicMock()

    result = ct.run()

    assert result['postrunjson']['Job']['Metrics_status'] == 'ok'
    assert 'Metrics_error' not in result['postrunjson']['Job']
    mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=[instance_id])


def test_disable_metrics_collection_skips_metrics_entirely(mocker):
    """disable_metrics_collection=True must skip metrics retrieval/plotting
    entirely (no CloudWatch/plot_metrics calls) while still succeeding and
    terminating.
    """
    jobid = 'myjob3'
    instance_id = 'i-0123456789abcdef2'
    prj_dict = _postrunjson_dict(jobid, instance_id)
    existing_keys = {'%s.job_started' % jobid, '%s.success' % jobid, '%s.postrun.json' % jobid}
    _mock_s3_layer(mocker, prj_dict, existing_keys)

    mock_ec2 = MagicMock()
    mocker.patch('tibanna.check_task.boto3.client', return_value=mock_ec2)

    ct = CheckTask(_make_check_task_input(jobid, instance_id, disable_metrics_collection=True))
    ct.TibannaResource = MagicMock()
    ct.API = MagicMock()

    result = ct.run()

    ct.TibannaResource.assert_not_called()
    ct.API.return_value.plot_metrics.assert_not_called()
    assert result['postrunjson']['Job']['Metrics_status'] == 'disabled'
    mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=[instance_id])
