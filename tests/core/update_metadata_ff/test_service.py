from core.update_metadata_ff.service import handler as ff
import pytest
from ..conftest import valid_env
import json


@valid_env
@pytest.mark.webtest
def test_run_update_metadata_ff_e2e(ff_meta_event_data, tibanna_env):
    ff_meta_event_data.update(tibanna_env)
    ret = ff(ff_meta_event_data, None)
    assert json.dumps(ret)
    assert ret['workflow']['task_input']
    assert ret['res']
    assert ret['ff_meta']
