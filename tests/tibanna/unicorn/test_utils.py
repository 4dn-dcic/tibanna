import pytest
import os
import shutil
import boto3
from tibanna.utils import (
    create_jobid,
    upload
)

def test_upload():
    randomstr = 'test-' + create_jobid()
    os.mkdir(randomstr)
    filepath = os.path.join(os.path.abspath(randomstr), randomstr)
    with open(filepath, 'w') as f:
        f.write('haha')
    upload(filepath, 'tibanna-output', 'uploadtest')
    s3 = boto3.client('s3')
    res = s3.get_object(Bucket='tibanna-output', Key='uploadtest/' + randomstr)
    assert res
    # cleanup afterwards
    shutil.rmtree(randomstr)
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': 'uploadtest/' + randomstr}]})
