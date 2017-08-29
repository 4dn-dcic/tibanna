from core.update_ffmeta_awsf.service import handler
# from core.check_export_sbg.service import get_inputfile_accession
import pytest
from ..conftest import valid_env
import json


@valid_env
@pytest.mark.webtest
def test_update_ffmeta_awsem_e2e(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    ret = handler(update_ffmeta_event_data, None)
    assert json.dumps(ret)
    assert ret['workflow']
