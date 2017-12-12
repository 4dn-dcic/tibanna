from core.run_task_sbg.service import handler
import pytest
from ..conftest import valid_env
import json


@valid_env
@pytest.mark.webtest
def test_run_task_sbg_e2e(run_task_event_data, tibanna_env):
    run_task_event_data.update(tibanna_env)
    return
    # this modifies data
    try:
        ret = handler(run_task_event_data, None)
    except Exception as exc:
        assert str(exc).startswith('Failed to create task')
    else:
        assert json.dumps(ret)
        assert ret['workflow']['task_input']
        assert ret['workflow']['task_id']
        assert ret['workflow']['output_volume_id']
        assert ret['run_response']
