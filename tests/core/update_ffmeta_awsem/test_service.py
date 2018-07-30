from core.update_ffmeta_awsem.service import (
    handler,
    get_postrunjson_url,
    register_to_higlass,
    md5_updater,
    _md5_updater
)
from core.pony_utils import Awsem
from core import pony_utils
# from core.check_export_sbg.service import get_inputfile_accession
import pytest
from ..conftest import valid_env
import json
import mock
import logging


LOG = logging.getLogger(__name__)


def test__md5_updater_1():
    inputjson = {'status': 'uploading',
                 'md5sum': '1234',
                 'content_md5sum': '5678'
                 }
    md5 = '1234'
    content_md5 = '5678'
    new_file = _md5_updater(inputjson, md5, content_md5)
    assert new_file == {}


def test__md5_updater_2():
    inputjson = {'status': 'uploading',
                 'md5sum': '1234',
                 'content_md5sum': '5678'
                 }
    md5 = None
    content_md5 = '5678'
    new_file = _md5_updater(inputjson, md5, content_md5)
    assert new_file == {}


def test__md5_updater_3():
    inputjson = {'status': 'uploading',
                 'md5sum': '1234',
                 'content_md5sum': '5678'
                 }
    md5 = '0000'
    content_md5 = '5678'
    new_file = _md5_updater(inputjson, md5, content_md5)
    assert new_file == "Failed"


def test__md5_updater_4():
    inputjson = {'status': 'uploading',
                 'md5sum': '1234',
                 'content_md5sum': '5678'
                 }
    md5 = '1234'
    content_md5 = '0000'
    new_file = _md5_updater(inputjson, md5, content_md5)
    assert new_file == 'Failed'


def test__md5_updater_5():
    inputjson = {'status': 'uploading',
                 'md5sum': '1234'
                 }
    md5 = '1234'
    content_md5 = '5678'
    new_file = _md5_updater(inputjson, md5, content_md5)
    assert new_file
    assert 'content_md5sum' in new_file
    assert new_file['content_md5sum'] == '5678'
    assert 'md5sum' not in new_file
    assert 'status' in new_file
    assert new_file['status'] == 'uploaded'


def test__md5_updater_6():
    inputjson = {'status': 'uploading',
                 'content_md5sum': '5678'
                 }
    md5 = '1234'
    content_md5 = '5678'
    new_file = _md5_updater(inputjson, md5, content_md5)
    assert new_file
    assert 'md5sum' in new_file
    assert new_file['md5sum'] == '1234'
    assert 'content_md5sum' not in new_file
    assert 'status' in new_file
    assert new_file['status'] == 'uploaded'


def test__md5_updater_7():
    inputjson = {'status': 'uploading',
                 'md5sum': '1234'
                 }
    md5 = None
    content_md5 = '5678'
    new_file = _md5_updater(inputjson, md5, content_md5)
    assert new_file
    assert 'content_md5sum' in new_file
    assert new_file['content_md5sum'] == '5678'
    assert 'md5sum' not in new_file
    assert 'status' in new_file
    assert new_file['status'] == 'uploaded'


def test__md5_updater_8():
    inputjson = {'status': 'uploaded',
                 'md5sum': '1234',
                 }
    md5 = '1234'
    content_md5 = '5678'
    new_file = _md5_updater(inputjson, md5, content_md5)
    assert new_file
    assert 'content_md5sum' in new_file
    assert new_file['content_md5sum'] == '5678'
    assert 'md5sum' not in new_file
    assert 'status' not in new_file


def test__md5_updater_extra_file():
    inputjson = {'status': 'uploaded',
                 'md5sum': '1234',
                 'extra_files': [
                   {
                     'file_format': 'pairs_px2'
                   }
                 ]
                 }
    md5 = '1234'
    content_md5 = '5678'
    new_file = _md5_updater(inputjson, md5, content_md5, format_if_extra='pairs_px2')
    assert new_file
    assert 'extra_files' in new_file
    assert new_file['extra_files'][0]['file_format'] == 'pairs_px2'
    assert new_file['extra_files'][0]['md5sum'] == '1234'
    assert new_file['extra_files'][0]['content_md5sum'] == '5678'
    assert 'md5sum' not in new_file
    assert 'content_md5sum' not in new_file
    assert 'status' not in new_file


@valid_env
@pytest.mark.webtest
def test_md5_updater_oldmd5(update_ffmeta_event_data):
    event = update_ffmeta_event_data
    tibanna_settings = event.get('_tibanna', {})
    tibanna = pony_utils.Tibanna(**tibanna_settings)
    awsem = Awsem(update_ffmeta_event_data)
    ouf = awsem.output_files()['report']
    md5_updater('uploaded', ouf, None, tibanna)


@valid_env
@pytest.mark.webtest
def test_md5_updater_newmd5(update_ffmeta_event_data_newmd5):
    event = update_ffmeta_event_data_newmd5
    tibanna_settings = event.get('_tibanna', {})
    tibanna = pony_utils.Tibanna(**tibanna_settings)
    awsem = Awsem(update_ffmeta_event_data_newmd5)
    ouf = awsem.output_files()['report']
    md5_updater('uploaded', ouf, None, tibanna)


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
def test_mcool_updates_fourfront_higlass(update_ffmeta_mcool, tibanna_env):
    update_ffmeta_mcool.update(tibanna_env)
    with mock.patch('core.pony_utils.patch_metadata'):
        with mock.patch('requests.post') as mock_request:
            ret = handler(update_ffmeta_mcool, None)
            mock_request.assert_called_once()
            assert ret


@valid_env
@pytest.mark.webtest
def test_metadata_only(update_ffmeta_metaonly_data2, tibanna_env):
    update_ffmeta_metaonly_data2.update(tibanna_env)
    with mock.patch('core.pony_utils.patch_metadata') as mock_request:
        ret = handler(update_ffmeta_metaonly_data2, None)
        # once for patch pf once for workflow run
        mock_request.call_count == 2
    assert ret


@pytest.mark.webtest
def test_register_to_higlass(used_env):
    bucket = 'elasticbeanstalk-fourfront-webdev-wfoutput'
    mcool_key = 'a940cf00-6001-473e-80d1-1e4a43866863/4DNFI75GAT6T.mcool'
    tibanna = pony_utils.Tibanna(used_env)
    with mock.patch('requests.post') as mock_request:
        res = register_to_higlass(tibanna, bucket, mcool_key, 'cooler', 'matrix')
        mock_request.assert_called_once()
        LOG.info(res)
        assert res


@pytest.mark.webtest
def test_register_to_higlass2(used_env):
    bucket = 'elasticbeanstalk-fourfront-webdev-wfoutput'
    bigwig_key = 'a940cf00-6001-473e-80d1-1e4a43866863/4DNFI75GAT6T.bw'
    tibanna = pony_utils.Tibanna(used_env)
    with mock.patch('requests.post') as mock_request:
        res = register_to_higlass(tibanna, bucket, bigwig_key, 'bigwig', 'vector')
        mock_request.assert_called_once()
        LOG.info(res)
        assert res
