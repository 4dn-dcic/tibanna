import pytest
from core.run_task_awsf import service
from ..conftest import valid_env


@valid_env
@pytest.mark.webtest
def test_run_awsem_handler(run_awsf_event_data):
    # data = service.handler(run_awsf_event_data, '')
    service.handler(run_awsf_event_data, '')
