import pytest
from tibanna_4dn.lambdas.run_task import handler
from tests.tibanna.pony.conftest import valid_env


@valid_env
@pytest.mark.webtest
def test_run_task_md5_reference_file(run_task_event_md5_fail):
    # invalid file name specified
    res = handler(run_task_event_md5_fail, None)
    assert(res)
    assert res.get('error')
