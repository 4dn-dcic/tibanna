from core.update_ffmeta_awsf.service import handler, add_postrunjson_to_ff_meta
# from core.check_export_sbg.service import get_inputfile_accession
import pytest
from ..conftest import valid_env
import json
import uuid


@valid_env
@pytest.mark.webtest
def test_add_postrunjson_to_ff_meta(update_ffmeta_event_data, tibanna_env, ff_keys):
    update_ffmeta_event_data.update(tibanna_env)
    att_uuid = add_postrunjson_to_ff_meta(update_ffmeta_event_data, ff_keys)
    assert att_uuid
    assert len(att_uuid) == len(str(uuid.uuid4()))


@valid_env
@pytest.mark.webtest
def test_update_ffmeta_awsem_e2e(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    ret = handler(update_ffmeta_event_data, None)
    assert json.dumps(ret)
    assert 'documents' in ret['ff_meta']
    assert ret['ff_meta']['documents']
    # test that file is uploaded?

'''
@valid_env
@pytest.mark.webtest
def test_pseudo_update_ffmeta_awsem_e2e(update_ffmeta_metaonly_data, tibanna_env):
    update_ffmeta_metaonly_data.update(tibanna_env)
    ret = handler(update_ffmeta_metaonly_data, None)
    assert json.dumps(ret)
    # test that file is uploaded?
'''
