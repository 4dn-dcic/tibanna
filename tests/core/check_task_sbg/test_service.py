from core.check_task_sbg.service import handler as check_task_handler
import pytest
from ..conftest import valid_env
import json


@valid_env
@pytest.mark.webtest
def test_check_task_sbg_e2e(check_task_event_data, tibanna_env):
    try:
        check_task_event_data.update(tibanna_env)
        ret = check_task_handler(check_task_event_data, None)
    except Exception as e:
        datastring = e.message.strip("Task not finished => ")
        import ast
        resp = ast.literal_eval(datastring)
        assert 'status' in resp.keys()
    else:
        assert json.dumps(ret)
        assert ret['workflow']['task_input']
        assert ret['workflow']['task_id']
        assert ret['workflow']['output_volume_id']
        assert ret['run_response']
        assert ret['run_response']['status'] in ['COMPLETED', 'DONE', 'FAILED']
        assert ret['_tibanna']
