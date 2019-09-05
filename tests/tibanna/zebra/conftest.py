import pytest
from dcicutils.s3_utils import s3Utils
import os
import json


def pytest_runtest_setup(item):
    # called for running each test in directory
    print("Running lambda tests for: ", item)


valid_env = pytest.mark.skipif(not os.environ.get("S3_ENCRYPT_KEY", False),
                               reason='Required environment not setup to run test')


@pytest.fixture(scope='session')
def start_run_event_md5():
    return get_event_file_for('start_run', event_file='event_md5.json')


def get_event_file_for(lambda_name, sbg_keys=None, ff_keys=None, event_file='event.json'):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    event_file_name = os.path.join(dir_path, lambda_name, event_file)
    return read_event_file(event_file_name, sbg_keys, ff_keys)


def read_event_file(event_file_name, sbg_keys=None, ff_keys=None):
    with open(event_file_name) as json_data:
        data = json.load(json_data)
        if sbg_keys is not None:
            data['token'] = sbg_keys
        if ff_keys is not None:
            data['ff_keys'] = ff_keys
        return data
                  
