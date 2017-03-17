from core.travis_deploy.service import handler as deploy_prod_handler
import pytest
import os


valid_travis_env = pytest.mark.skipif(not os.environ.get("travis_key", False),
                                      reason='Required environment not setup to run test')


@pytest.fixture
def repo():  # pylint: disable=fixme
    return {'branch': 'test',
            'repo_owner': '4dn-dcic',
            'repo_name': 'tibanna'
            }


@valid_travis_env
def test_deploy_prod(repo):
    res = deploy_prod_handler(repo, None)
    print(res)
