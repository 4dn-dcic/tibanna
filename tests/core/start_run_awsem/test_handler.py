import pytest
from core.start_run_awsf import service
from ..conftest import valid_env


@valid_env
@pytest.mark.webtest
def test_start_awsem_handler(run_awsf_event_data):
    data = service.handler(run_awsf_event_data, '')
