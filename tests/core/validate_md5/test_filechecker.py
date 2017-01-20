import pytest
from core.validate_md5 import filechecker
import json


@pytest.fixture
def put_file_event_data():
    return {
             "Records": [
               {
                "eventVersion": "2.0",
                "eventTime": "1970-01-01T00:00:00.000Z",
                "requestParameters": {
                        "sourceIPAddress": "127.0.0.1"
                },
                "s3": {
                        "configurationId": "testConfigRule",
                        "object": {
                                "eTag": "2bf4be44f663da165d1a2c36b97bafdd",
                                "sequencer": "0A1B2C3D4E5F678901",
                                "key": "test_upload/4DNFI7RAJFJ4.fasta.gz",
                                "size": 434478
                        },
                        "bucket": {
                            "arn": "arn:aws:s3:::elasticbeanstalk-encoded-4dn-files",
                            "name": "elasticbeanstalk-encoded-4dn-files",
                            "ownerIdentity": {
                                 "principalId": "EXAMPLE"
                             }
                        },
                        "s3SchemaVersion": "1.0"
                },
                "responseElements": {
                        "x-amz-id-2": "EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH",
                        "x-amz-request-id": "EXAMPLE123456789"
                },
                "awsRegion": "us-east-1",
                "eventName": "ObjectCreated:Put",
                "userIdentity": {
                        "principalId": "EXAMPLE"
                },
                "eventSource": "aws:s3"
              }  # noqa
            ]  # noqa
         }


def test_build_req_parameters(put_file_event_data):
    params = json.loads(
        filechecker.build_req_parameters(put_file_event_data))
    assert params['app_name'] == 'md5'
    input_file = params['input_files'][0]
    assert input_file['bucket_name'] == 'elasticbeanstalk-encoded-4dn-files'
    assert input_file['object_key'] == '4DNFI7RAJFJ4.fasta.gz'
    assert input_file['uuid'] == 'test_upload'
