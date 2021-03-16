import pytest
import os
import json


def pytest_runtest_setup(item):
    # called for running each test in directory
    print("Running lambda tests for: ", item)


@pytest.fixture()
def run_task_awsem_event_data():
    return get_event_file_for('run_task_awsem')


@pytest.fixture()
def run_task_awsem_event_omit_fields():
    return get_event_file_for('run_task_awsem', event_file='event_omit_fields.json')


@pytest.fixture()
def run_task_awsem_event_omit_fields2():
    return get_event_file_for('run_task_awsem', event_file='event_omit_fields2.json')


@pytest.fixture()
def run_task_awsem_event_data2():
    return get_event_file_for('run_task_awsem', event_file='event_repliseq.json')


@pytest.fixture()
def run_task_awsem_event_data_chipseq():
    return get_event_file_for('run_task_awsem', event_file='event_chipseq.json')


@pytest.fixture()
def run_task_awsem_event_cwl_upload():
    return get_event_file_for('run_task_awsem', event_file='event_cwl_upload.json')


@pytest.fixture()
def run_task_awsem_event_wdl_md5_benchmark_error():
    return get_event_file_for('run_task_awsem', event_file='event_wdl_md5_benchmark_error.json')


@pytest.fixture()
def run_task_awsem_event_wdl_md5_do_not_use_benchmark():
    return get_event_file_for('run_task_awsem', event_file='event_wdl_md5_do_not_use_benchmark.json')


def get_test_json(file_name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    event_file_name = os.path.join(dir_path, '..', '..', '..', 'test_json', 'unicorn', file_name)
    return read_event_file(event_file_name, None)


def get_event_file_for(lambda_name, sbg_keys=None, event_file='event.json'):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    event_file_name = os.path.join(dir_path, lambda_name, event_file)
    return read_event_file(event_file_name, sbg_keys)


def read_event_file(event_file_name, sbg_keys=None):
    with open(event_file_name) as json_data:
        data = json.load(json_data)
        if sbg_keys is not None:
            data['token'] = sbg_keys
        return data
