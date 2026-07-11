import os
from unittest.mock import MagicMock
from tibanna.utils import upload, put_object_s3


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
