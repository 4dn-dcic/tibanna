from tibanna_ffcommon.portal_utils import (
    TibannaSettings,
    FormatExtensionMap,
)
from tibanna_4dn.pony_utils import (
    WorkflowRunMetadata,
    merge_source_experiments,
    ProcessedFileMetadata,
    get_extra_file_key,
    create_ffmeta_input_files_from_pony_input_file_list
)
import pytest
from tests.tibanna.pony.conftest import valid_env
from tibanna.utils import printlog
import mock


@valid_env
def test_tibanna():
    data = {'env': 'fourfront-webdev',
            'settings': {'1': '1'}}
    tibanna = TibannaSettings(**data)
    assert tibanna
    assert tibanna.as_dict() == data


@valid_env
@pytest.mark.webtest
def test_format_extension_map():
    data = {'env': 'fourfront-cgap',
            'settings': {'1': '1'}}
    tibanna = TibannaSettings(**data)
    fe_map = FormatExtensionMap(tibanna.ff_keys)
    assert(fe_map)
    assert 'bwt' in fe_map.fe_dict.keys()


def test_create_workflowrun_from_event_parameter(update_ffmeta_event_data_newmd5):
    meta = update_ffmeta_event_data_newmd5['ff_meta'].copy()
    meta['app_name'] = 'md5'
    ff_wfr = WorkflowRunMetadata(**meta)
    assert ff_wfr


@pytest.fixture()
def proc_file_in_webdev():
    return {'status': 'released',
            'uuid': 'f6d5ba22-aaf9-48e9-8df4-bc5c131c96af',
            'file_format': 'normvector_juicerformat',
            'accession': '4DNFIRO3UX7I',
            'award': '/awards/1U01CA200059-01/',
            'lab': '/labs/4dn-dcic-lab/'}


def test_create_ProcessedFileMetadata_from_get_error_if_no_at_type(ff_keys, proc_file_in_webdev):
    # can use acc, uuid, @id, any valid url
    with mock.patch('tibanna_4dn.pony_utils.get_metadata', return_value=proc_file_in_webdev):
        with pytest.raises(Exception) as expinfo:
            ProcessedFileMetadata.get(proc_file_in_webdev['accession'], ff_keys)
        assert "only load ProcessedFiles" in str(expinfo.value)


def test_create_ProcessedFileMetadata_from_get(ff_keys, proc_file_in_webdev):
    # can use acc, uuid, @id, any valid url
    file_with_type = proc_file_in_webdev.copy()
    file_with_type['@type'] = ['FileProcessed', 'Item', 'whatever']
    with mock.patch('tibanna_4dn.pony_utils.get_metadata', return_value=file_with_type) as ff:
        pf = ProcessedFileMetadata.get(proc_file_in_webdev['accession'], ff_keys)
        assert pf.as_dict() == proc_file_in_webdev
        assert type(pf) is ProcessedFileMetadata
        ff.was_called_once()


@valid_env
@pytest.mark.webtest
def test_merge_source_experiment(run_awsem_event_data):
    input_file = {
        "bucket_name": "elasticbeanstalk-fourfront-webdev-wfoutput",
        "workflow_argument_name": "input_pairs",
        "uuid": ["d2c897ec-bdb2-47ce-b1b1-845daccaa571", "d2c897ec-bdb2-47ce-b1b1-845daccaa571"],
        "object_key": ["4DNFI25JXLLI.pairs.gz", "4DNFI25JXLLI.pairs.gz"]
    }
    data = run_awsem_event_data
    tibanna_settings = data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = TibannaSettings(env, ff_keys=data.get('ff_keys'),
                              settings=tibanna_settings)
    res = merge_source_experiments(input_file['uuid'], tibanna.ff_keys, tibanna.env)
    printlog(res)
    assert 'fake_source_experiment' in res


@valid_env
@pytest.mark.webtest
def test_get_extra_file_key(run_awsem_event_data):
    tibanna_settings = run_awsem_event_data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = TibannaSettings(env, ff_keys=run_awsem_event_data.get('ff_keys'),
                              settings=tibanna_settings)
    fe_map = FormatExtensionMap(tibanna.ff_keys)
    infile_key = 'hahaha/lalala.bedGraph.gz'
    infile_format = 'bg'
    extra_file_format = 'bw'
    extra_file_key = get_extra_file_key(infile_format, infile_key, extra_file_format, fe_map)
    assert extra_file_key == 'hahaha/lalala.bw'
