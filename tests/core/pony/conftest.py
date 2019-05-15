import pytest
from dcicutils.s3_utils import s3Utils
import os
import json


def pytest_runtest_setup(item):
    # called for running each test in directory
    print("Running lambda tests for: ", item)


valid_env = pytest.mark.skipif(not os.environ.get("SECRET", False),
                               reason='Required environment not setup to run test')


@pytest.fixture(scope='session')
def used_env():
    return 'fourfront-webdev'


@pytest.fixture(scope='session')
def tibanna_env(used_env):
    return {'_tibanna': {'env': used_env}}


@pytest.fixture(scope='session')
def s3_utils(used_env):
    return s3Utils(env=used_env)


@pytest.fixture(scope='session')
def ff_keys(s3_utils):
    return s3_utils.get_access_keys()


@pytest.fixture(scope='session')
def s3_trigger_event_data():
    return get_event_file_for('validate_md5_s3_trigger')


@pytest.fixture(scope='session')
def s3_trigger_event_data_pf():
    return get_event_file_for('validate_md5_s3_trigger', event_file='event_pf.json')


@pytest.fixture(scope='session')
def s3_trigger_event_data_pf_extra_status():
    return get_event_file_for('validate_md5_s3_trigger', event_file='event_pf_extra_status.json')


@pytest.fixture(scope='session')
def md5_event_data():
    # I want this to go through the tibanna env lookup, to ensure it gets
    # appropriate keys
    return get_test_json('md5_input.json')


@pytest.fixture(scope='session')
def export_files_event_data(sbg_keys, ff_keys):
    return get_event_file_for('export_files_sbg', sbg_keys, ff_keys)


@pytest.fixture(scope='session')
def check_export_event_data(sbg_keys, ff_keys):
    return get_event_file_for('check_export_sbg', sbg_keys, ff_keys)


@pytest.fixture(scope='session')
def run_awsem_event_data(ff_keys):
    return get_event_file_for('start_run_awsem', ff_keys=ff_keys)


@pytest.fixture(scope='session')
def run_task_awsem_pseudo_workflow_event_data(ff_keys):
    return get_event_file_for('start_run_awsem', ff_keys=ff_keys, event_file='event_metadata_only.json')


@pytest.fixture(scope='session')
def run_awsem_event_data_secondary_files(ff_keys):
    return get_event_file_for('start_run_awsem', ff_keys=ff_keys, event_file='event_hicprocessingpartb.json')


@pytest.fixture(scope='session')
def run_awsem_event_data_processed_files(ff_keys):
    return get_event_file_for('start_run_awsem', ff_keys=ff_keys,
                              event_file='event_hicprocessingbam_customfield_wArgname.json')


@pytest.fixture(scope='session')
def run_awsem_event_data_processed_files2(ff_keys):
    return get_event_file_for('start_run_awsem', ff_keys=ff_keys,
                              event_file='event_hicprocessingbam_customfield_wALL.json')


@pytest.fixture(scope='session')
def update_ffmeta_event_data(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys)


@pytest.fixture(scope='session')
def update_ffmeta_event_data_extra_md5(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys, event_file='event_extra_md5.json')


@pytest.fixture(scope='session')
def update_ffmeta_event_data_newmd5(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys, event_file='event_newmd5.json')


@pytest.fixture(scope='session')
def update_ffmeta_event_data_pairsqc(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys, event_file='event_pairsqc.json')


@pytest.fixture(scope='session')
def update_ffmeta_mcool(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys, event_file='event_mcool.json')


@pytest.fixture(scope='session')
def update_ffmeta_event_data_fastqc(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys, event_file='event_fastqc.json')


@pytest.fixture(scope='session')
def update_ffmeta_metaonly_data(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys, event_file='event_metadataonly.json')


@pytest.fixture(scope='session')
def update_ffmeta_metaonly_data2(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys, event_file='event_metadata_2.json')


@pytest.fixture(scope='session')
def update_ffmeta_tmpdata(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys, event_file='event_tmp.json')


@pytest.fixture(scope='session')
def update_ffmeta_hicbam(ff_keys):
    return get_event_file_for('update_ffmeta_awsem', ff_keys=ff_keys, event_file='event_hicbam.json')


def get_test_json(file_name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    event_file_name = os.path.join(dir_path, '..', '..', '..', 'test_json', 'pony', file_name)
    return read_event_file(event_file_name, None, ff_keys)


def get_event_file_for(lambda_name, sbg_keys=None, ff_keys=None, event_file='event.json'):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    event_file_name = os.path.join(dir_path, '..', '..', '..', 'core', lambda_name, event_file)
    return read_event_file(event_file_name, sbg_keys, ff_keys)


def read_event_file(event_file_name, sbg_keys=None, ff_keys=None):
    with open(event_file_name) as json_data:
        data = json.load(json_data)
        if sbg_keys is not None:
            data['token'] = sbg_keys
        if ff_keys is not None:
            data['ff_keys'] = ff_keys
        return data
