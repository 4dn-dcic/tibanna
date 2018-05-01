import pytest
from core.run_task_awsem.service import handler
from ..conftest import valid_env


@valid_env
@pytest.mark.webtest
def test_run_task_md5_reference_file(run_task_awsem_event_md5):
    # invalid file name specified
    res = handler(run_task_awsem_event_md5, None)
    assert(res)
    assert res.get('error')
