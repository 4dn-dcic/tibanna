# from core.tibanna_slackbot.service import lambda_handler as handler
from core.tibanna_slackbot.service import giphy
import pytest
from ..conftest import valid_env
# import json


@valid_env
@pytest.mark.webtest
def test_giphy():
    url = giphy("testing")
    print(url)
    assert url
'''def test_check_import_sbg_e2e(check_import_event_data):
    ret = handler(check_import_event_data, None)
    assert json.dumps(ret)
    assert ret['workflow']['task_input']
    assert ret['ff_meta']
    assert ret['workflow']['output_volume_id']
    # since we know files are imported now, make sure that info is in ff_meta
    assert ret['ff_meta']['sbg_mounted_volume_ids']
'''
