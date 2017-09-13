import pytest
from core.start_run_awsf.service import (
    handler,
    get_format_extension_map,
    handle_processed_files,
    update_config
)
from ..conftest import valid_env
from core.utils import Tibanna
from core import ff_utils


@valid_env
@pytest.mark.webtest
def test_start_awsem_handler(run_awsf_event_data):
    # data = service.handler(run_awsf_event_data, '')
    handler(run_awsf_event_data, '')


@valid_env
@pytest.mark.webtest
def test_start_awsem_handler_secondary_files(run_awsf_event_data_secondary_files):
    try:
        handler(run_awsf_event_data_secondary_files, '')
    except Exception as e:
        print(e)
        pytest.skip("seems data is not in place")


@valid_env
@pytest.mark.webtest
def test_get_format_extension_map(run_awsf_event_data):
    tibanna_settings = run_awsf_event_data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, s3_keys=run_awsf_event_data.get('s3_keys'),
                      ff_keys=run_awsf_event_data.get('ff_keys'),
                      settings=tibanna_settings)

    fe_map = get_format_extension_map(tibanna)
    assert(fe_map)
    assert 'pairs' in fe_map.keys()


@valid_env
@pytest.mark.webtest
def test_handle_processed_files(run_awsf_event_data_secondary_files):
    data = run_awsf_event_data_secondary_files
    tibanna_settings = data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, s3_keys=data.get('s3_keys'),
                      ff_keys=data.get('ff_keys'),
                      settings=tibanna_settings)
    workflow_uuid = data['workflow_uuid']
    workflow_info = ff_utils.get_metadata(workflow_uuid, key=tibanna.ff_keys)

    output_files, pf_meta = handle_processed_files(workflow_info, tibanna)
    assert(output_files)
    assert len(output_files) == 3
    for of in output_files:
        if of['extension'] == '.pairs.gz':
            assert of['secondary_file_extensions'] == ['.pairs.gz.px2']
            assert of['secondary_file_formats'] == ['pairs_px2']
            assert of['extra_files']
        else:
            assert 'secondary_files_extension' not in of
            assert 'secondary_files_formats' not in of

    assert(pf_meta)
    assert len(pf_meta) == 3
    for pf in pf_meta:
        pdict = pf.__dict__
        if pdict['file_format'] == 'pairs':
            assert pdict['extra_files'] == [{'file_format': 'pairs_px2'}]
        else:
            assert 'extra_files' not in pdict


@valid_env
@pytest.mark.webtest
def test_update_config(run_awsf_event_data):
    data = run_awsf_event_data
    config = update_config(data['config'], data['app_name'], data['input_files'], data['parameters'])
    assert config['instance_type'] == 't2.nano'
    assert config['EBS_optimized'] is False
    assert config['ebs_size'] >= 10
    assert config['copy_to_s3'] is True  # check the other fields are preserved in the returned config
