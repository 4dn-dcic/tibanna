from dcicutils import ff_utils, tibanna_utils
import pytest
import mock
from .conftest import valid_env
from core.utils import Tibanna
import logging

LOG = logging.getLogger(__name__)


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
    with mock.patch('dcicutils.ff_utils.get_metadata', return_value=proc_file_in_webdev):
        with pytest.raises(Exception) as expinfo:
            tibanna_utils.ProcessedFileMetadata.get(proc_file_in_webdev['accession'], ff_keys)
        assert "only load ProcessedFiles" in str(expinfo.value)


def test_create_ProcessedFileMetadata_from_get(ff_keys, proc_file_in_webdev):
    # can use acc, uuid, @id, any valid url
    file_with_type = proc_file_in_webdev.copy()
    file_with_type['@type'] = ['FileProcessed', 'Item', 'whatever']
    with mock.patch('dcicutils.ff_utils.get_metadata', return_value=file_with_type) as ff:
        pf = tibanna_utils.ProcessedFileMetadata.get(proc_file_in_webdev['accession'], ff_keys)
        assert pf.__dict__ == proc_file_in_webdev
        assert type(pf) is ProcessedFileMetadata
        ff.was_called_once()


@valid_env
@pytest.mark.webtest
def test_get_format_extension_map(run_awsem_event_data):
    tibanna_settings = run_awsem_event_data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, ff_keys=run_awsem_event_data.get('ff_keys'),
                      settings=tibanna_settings)

    fe_map = tibanna_utils.get_format_extension_map(tibanna.ff_keys)
    assert(fe_map)
    assert 'pairs' in fe_map.keys()


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
    tibanna = Tibanna(env, ff_keys=data.get('ff_keys'),
                      settings=tibanna_settings)
    res = tibanna_utils.merge_source_experiments(input_file['uuid'], tibanna.ff_keys)
    LOG.info(res)
    assert 'fake_source_experiment' in res


def test_get_extra_file_key():
    fe_map = {'bg': '.bedGraph.gz', 'bw': '.bw'}
    infile_key = 'hahaha/lalala.bedGraph.gz'
    infile_format = 'bg'
    extra_file_format = 'bw'
    extra_file_key = tibanna_utils.get_extra_file_key(infile_format, infile_key, extra_file_format, fe_map)
    assert extra_file_key == 'hahaha/lalala.bw'
