from tibanna_4dn.lambdas.update_ffmeta_awsem import (
    handler,
    real_handler
)
from tibanna_4dn.pony_utils import ProcessedFileMetadata
from tibanna_4dn.pony_utils import TibannaSettings
from tibanna.utils import printlog
# from tibanna.check_export_sbg import get_inputfile_accession
import pytest
from ..conftest import valid_env
import json
import mock
from dcicutils import ff_utils


@valid_env
@pytest.mark.webtest
def test_tmp(update_ffmeta_tmpdata, tibanna_env):
    update_ffmeta_tmpdata.update(tibanna_env)
    with mock.patch('tibanna_4dn.pony_utils.patch_metadata') as mock_request:
        ret = real_handler(update_ffmeta_tmpdata, None)
        mock_request.call_count == 3
    printlog(ret)
    # once for patch pf once for workflow run
    assert ret


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
def test_update_ffmeta_awsem_extra_md5(update_ffmeta_hicbam, tibanna_env):
    update_ffmeta_hicbam.update(tibanna_env)
    ret = handler(update_ffmeta_hicbam, None)
    assert json.dumps(ret)
    assert 'awsem_postrun_json' in ret['ff_meta']
    assert ret['ff_meta']['awsem_postrun_json'] == 'https://s3.amazonaws.com/tibanna-output/x2w1uKSsEvT0.postrun.json'
    assert 'md5sum' in ret['pf_meta'][1]['extra_files'][0]
    assert 'file_size' in ret['pf_meta'][1]['extra_files'][0]


@valid_env
def test_mcool_updates_fourfront_higlass(update_ffmeta_mcool, tibanna_env):
    update_ffmeta_mcool.update(tibanna_env)
    with mock.patch('tibanna_4dn.pony_utils.patch_metadata'):
        with mock.patch('requests.post') as mock_request:
            ret = handler(update_ffmeta_mcool, None)
            mock_request.assert_called_once()
            assert ret


@valid_env
@pytest.mark.webtest
def test_metadata_only(update_ffmeta_metaonly_data2, tibanna_env):
    update_ffmeta_metaonly_data2.update(tibanna_env)
    with mock.patch('tibanna_4dn.pony_utils.patch_metadata') as mock_request:
        ret = handler(update_ffmeta_metaonly_data2, None)
        # once for patch pf once for workflow run
        mock_request.call_count == 2
    assert ret


@pytest.mark.webtest
def test_register_to_higlass(used_env):
    bucket = 'elasticbeanstalk-fourfront-webdev-wfoutput'
    mcool_key = 'a940cf00-6001-473e-80d1-1e4a43866863/4DNFI75GAT6T.mcool'
    tbn = TibannaSettings(used_env)
    with mock.patch('requests.post') as mock_request:
        res = register_to_higlass(tbn, bucket, mcool_key, 'cooler', 'matrix')
        mock_request.assert_called_once()
        printlog(res)
        assert res


@pytest.mark.webtest
def test_register_to_higlass2(used_env):
    bucket = 'elasticbeanstalk-fourfront-webdev-wfoutput'
    bigwig_key = 'a940cf00-6001-473e-80d1-1e4a43866863/4DNFI75GAT6T.bw'
    tbn = TibannaSettings(used_env)
    with mock.patch('requests.post') as mock_request:
        res = register_to_higlass(tbn, bucket, bigwig_key, 'bigwig', 'vector')
        mock_request.assert_called_once()
        printlog(res)
        assert res


@pytest.mark.webtest
def test_register_to_higlass3(used_env):
    bucket = 'elasticbeanstalk-fourfront-webdev-wfoutput'
    bigbed_key = 'a34d5ea5-eada-4def-a4a7-c227b0d32395/4DNFIC624FKJ.bb'
    tbn = TibannaSettings(used_env)
    with mock.patch('requests.post') as mock_request:
        res = register_to_higlass(tbn, bucket, bigbed_key, 'bigwig', 'vector')
        mock_request.assert_called_once()
    printlog(res)
    assert res


@valid_env
@pytest.mark.webtest
def test__input_extra_updater():
    tbn = TibannaSettings('fourfront-webdev',
                          settings={"run_type": "bedGraphToBigWig",
                                    "env": "fourfront-webdev"})
    accession = '4DNFIF14KRAK'
    _input_extra_updater('uploaded', tbn, accession, 'bw', 'some_md5', 1234, 'some_higlass_uid')
    res = ff_utils.get_metadata(accession, tbn.ff_keys, tbn.env,
                                add_on='frame=object', check_queue=True)
    assert res['extra_files'][0]['file_format'] == '/file-formats/bw/'
    assert res['extra_files'][0]['status'] == 'uploaded'
    assert res['extra_files'][0]['md5sum'] == 'some_md5'
    assert res['extra_files'][0]['file_size'] == 1234
    assert res['higlass_uid'] == 'some_higlass_uid'
    _input_extra_updater('upload failed', tbn, '4DNFIF14KRAK', 'bw', 'some_other_md5', 5678)
    res = ff_utils.get_metadata(accession, tbn.ff_keys, tbn.env,
                                add_on='frame=object', check_queue=True)
    assert res['extra_files'][0]['file_format'] == '/file-formats/bw/'
    assert res['extra_files'][0]['status'] == 'upload failed'
    assert res['extra_files'][0]['md5sum'] == 'some_md5'
    assert res['extra_files'][0]['file_size'] == 1234
    with pytest.raises(Exception) as expinfo:
        _input_extra_updater('uploaded', tbn, accession, 'lalala')
        assert "inconsistency - extra file metadata deleted during workflow run?" in str(expinfo.value)
