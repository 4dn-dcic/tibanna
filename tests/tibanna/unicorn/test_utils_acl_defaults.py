import os
from unittest.mock import MagicMock
from tibanna.utils import upload, put_object_s3
from tibanna.ec2_utils import Execution


def test_upload_defaults_to_private_acl(mocker, tmp_path):
    """K1/R8 regression: upload() must default to a private object, not
    public-read, so a caller that forgets to pass public=False does not
    accidentally publish a metrics/cost/marker/run/postrun artifact.
    """
    mock_s3 = MagicMock()
    mocker.patch('tibanna.utils.boto3.client', return_value=mock_s3)

    filepath = os.path.join(tmp_path, 'somefile')
    with open(filepath, 'w') as f:
        f.write('content')

    upload(filepath, 'somebucket', 'someprefix')

    _, kwargs = mock_s3.upload_file.call_args
    assert kwargs['ExtraArgs']['ACL'] == 'private'


def test_upload_no_filepath_defaults_to_private_acl(mocker):
    mock_s3 = MagicMock()
    mocker.patch('tibanna.utils.boto3.client', return_value=mock_s3)

    upload(None, 'somebucket', 'someprefix/lock')

    _, kwargs = mock_s3.put_object.call_args
    assert kwargs['ACL'] == 'private'


def test_put_object_s3_defaults_to_private_acl(mocker):
    mock_s3 = MagicMock()
    mocker.patch('tibanna.utils.boto3.client', return_value=mock_s3)

    put_object_s3('some content', 'somekey', 'somebucket')

    _, kwargs = mock_s3.put_object.call_args
    assert kwargs['ACL'] == 'private'


def test_upload_public_still_available_as_explicit_opt_in(mocker, tmp_path):
    """Public output remains available, but only via an explicit public=True
    call - never as a silent default."""
    mock_s3 = MagicMock()
    mocker.patch('tibanna.utils.boto3.client', return_value=mock_s3)

    filepath = os.path.join(tmp_path, 'somefile')
    with open(filepath, 'w') as f:
        f.write('content')

    upload(filepath, 'somebucket', 'someprefix', public=True)

    _, kwargs = mock_s3.upload_file.call_args
    assert kwargs['ExtraArgs']['ACL'] == 'public-read'


def test_upload_run_json_defaults_to_private(mocker):
    """K1/R8: upload_run_json() writes the run.json artifact via a raw
    put_object call with no ACL argument, which is private-by-default in S3 -
    pin that explicitly, since put_object's default silently changes to
    public if anyone ever adds a bucket-level public ACL policy upstream.
    """
    mock_ec2 = MagicMock()
    mock_ec2.describe_instance_types.return_value = {
        'InstanceTypes': [{
            'InstanceType': 't3.micro',
            'EbsInfo': {'EbsOptimizedSupport': 'default'},
            'ProcessorInfo': {'SupportedArchitectures': ['x86_64']},
        }]
    }
    mock_s3 = MagicMock()

    def _client(service, *args, **kwargs):
        return mock_ec2 if service == 'ec2' else mock_s3

    mocker.patch('tibanna.ec2_utils.boto3.client', side_effect=_client)
    input_dict = {
        'args': {
            'input_files': {},
            'output_S3_bucket': 'somebucket',
            'app_name': 'md5',
            'cwl_main_filename': 'md5.cwl',
            'cwl_directory_url': 'someurl',
        },
        'config': {'log_bucket': 'somebucket', 'instance_type': 't3.micro', 'ebs_size': 20},
        'jobid': 'myjobid',
    }
    execution = Execution(input_dict)

    execution.upload_run_json({'some': 'runjson'})

    _, kwargs = mock_s3.put_object.call_args
    assert 'ACL' not in kwargs
