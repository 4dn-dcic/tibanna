from core.check_export_sbg.service import handler as check_export_handler
import pytest
from ..conftest import valid_env
import json


@valid_env
@pytest.mark.webtest
def test_check_export_fastqc_e2e(check_export_event_data):
    check_export_event_data['workflow']['app_name'] = 'fastqc-0-11-4-1'
    try:
        import pdb
        pdb.set_trace()
        ret = check_export_handler(check_export_event_data, None)
    except Exception as e:
        if "409" in e:
            # duplicate UUID, just ignore that
            return
        raise e
    assert json.dumps(ret)
    assert ret['workflow']


@valid_env
@pytest.mark.webtest
def test_check_export_sbg_e2e(check_export_event_data):
    try:
        ret = check_export_handler(check_export_event_data, None)
    except Exception as e:
        if "409" in e:
            # duplicate UUID, just ignore that
            return
        raise e
    assert json.dumps(ret)
    assert ret['workflow']
    # assert ret['ff_meta']['output_files']
    # assert ret['ff_meta']['sbg_export_ids']
