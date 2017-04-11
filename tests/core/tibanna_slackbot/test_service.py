# from core.tibanna_slackbot.service import lambda_handler as handler
from core.tibanna_slackbot.service import giphy
from core.tibanna_slackbot.build import BuildStatus
import pytest
from ..conftest import valid_env
# import json


@valid_env
@pytest.mark.webtest
def test_giphy():
    url = giphy("testing")
    print(url)
    assert url


@valid_env
@pytest.mark.webtest
def test_build_status():
    assert BuildStatus.name == '/ffstatus'


@valid_env
@pytest.mark.webtest
def test_build_status_run():
    print(BuildStatus().run())
    assert 0
