from core.check_import_sbg.service import handler
import pytest
from ..conftest import valid_env
import json


@valid_env
@pytest.mark.webtest
def test_check_import_sbg_e2e(check_import_event_data):
    ret = handler(check_import_event_data, None)
    assert json.dumps(ret)
    assert ret['workflow']['task_input']
    assert ret['metadata_input']
