import pytest
from core import sbg_utils
import os
import json


def pytest_runtest_setup(item):
    # called for running each test in directory
    print ("Running lambda tests for: ", item)


valid_env = pytest.mark.skipif(not os.environ.get("SECRET", False),
                               reason='Required environment not setup to run test')


@pytest.fixture(scope='session')
def s3_keys():
    return sbg_utils.get_s3_keys()


@pytest.fixture(scope='session')
def sbg_keys():
    return sbg_utils.get_sbg_keys()


@pytest.fixture(scope='session')
def ff_keys():
    return sbg_utils.get_access_keys()


@pytest.fixture(scope='session')
def check_import_event_data(sbg_keys):
    return get_event_file_for('check_import_sbg', sbg_keys)


@pytest.fixture(scope='session')
def run_task_event_data(sbg_keys):
    return get_event_file_for('run_task_sbg', sbg_keys)


@pytest.fixture(scope='session')
def check_task_event_data(sbg_keys):
    return get_event_file_for('check_task_sbg', sbg_keys)


@pytest.fixture(scope='session')
def s3_trigger_event_data(sbg_keys):
    return get_event_file_for('validate_md5_s3_trigger', sbg_keys)


@pytest.fixture(scope='session')
def ff_meta_event_data(sbg_keys, ff_keys):
    return get_event_file_for('update_metadata_ff', sbg_keys, ff_keys)


@pytest.fixture(scope='session')
def export_files_event_data(sbg_keys, ff_keys):
    return get_event_file_for('export_files_sbg', sbg_keys, ff_keys)


@pytest.fixture(scope='session')
def check_export_event_data(sbg_keys, ff_keys):
    return get_event_file_for('check_export_sbg', sbg_keys, ff_keys)


def get_event_file_for(lambda_name, sbg_keys, ff_keys=None):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    event_file_name = os.path.join(dir_path, '..', '..', 'core', lambda_name, 'event.json')
    with open(event_file_name) as json_data:
        data = json.load(json_data)
        data['token'] = sbg_keys
        if ff_keys:
            data['ff_keys'] = ff_keys
        return data
