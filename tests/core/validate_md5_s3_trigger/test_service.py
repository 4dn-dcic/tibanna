from core.validate_md5_s3_trigger.service import handler as validate_md5_s3_trigger
from core.validate_md5_s3_trigger.service import make_input
# from core.validate_md5_s3_trigger.service import STEP_FUNCTION_ARN
import pytest
from ..conftest import valid_env
import json
import boto3


def test_build_req_parameters(s3_trigger_event_data):
    params = json.loads(
        make_input(s3_trigger_event_data))
    assert params['app_name'] == 'md5'
    input_file = params['input_files'][0]
    assert input_file['bucket_name'] == 'elasticbeanstalk-encoded-4dn-files'
    assert input_file['object_key'] == '4DNFI7RAJFJ4.fasta.gz'
    assert input_file['uuid'] == 'test_upload'


@valid_env
@pytest.mark.webtest
def test_s3_trigger_e2e(s3_trigger_event_data):
    ret = validate_md5_s3_trigger(s3_trigger_event_data, None)
    assert ret
    assert ret['ResponseMetadata']['HTTPStatusCode'] == 200
    executionArn = ret['executionArn']

    # see if task is running and kill it
    client = boto3.client('stepfunctions')
    run_details = client.describe_execution(
        executionArn=executionArn
    )
    assert run_details['status'] == 'RUNNING'

    client.stop_execution(
        executionArn=executionArn,
        error='test-run',
        cause='test run stuff',
    )
