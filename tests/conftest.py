import pytest

def pytest_addoption(parser):
    parser.addoption("--no-post")


@pytest.fixture
def no_post(request):
    return request.config.getoption("--no-post")


post = pytest.mark.skipif(no_post,
                          reason='Do not create actual portal objects')

