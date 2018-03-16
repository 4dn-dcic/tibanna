from core.update_ffmeta_awsem.service import handler, get_postrunjson_url
# from core.check_export_sbg.service import get_inputfile_accession
import pytest
from ..conftest import valid_env
import json
import mock


@valid_env
@pytest.mark.webtest
def test_get_postrunjson_url(update_ffmeta_event_data):
    url = get_postrunjson_url(update_ffmeta_event_data)
    assert url == 'https://s3.amazonaws.com/tibanna-output/8fRIlIfwRNDT.postrun.json'


@valid_env
@pytest.mark.webtest
def test_update_ffmeta_awsem_e2e(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    ret = handler(update_ffmeta_event_data, None)
    assert json.dumps(ret)
    assert 'awsem_postrun_json' in ret['ff_meta']
    assert ret['ff_meta']['awsem_postrun_json'] == 'https://s3.amazonaws.com/tibanna-output/8fRIlIfwRNDT.postrun.json'
    # test that file is uploaded?


@valid_env
@pytest.mark.webtest
def test_mcool_updates_fourfront_higlass(update_ffmeta_mcool, tibanna_env):
    update_ffmeta_mcool.update(tibanna_env)
    with mock.patch('core.ff_utils.post_to_metadata'):
        with mock.patch('requests.post') as mock_request:
            ret = handler(update_ffmeta_mcool, None)
            mock_request.assert_called_once()
            assert json.dumps(ret)
