from unittest.mock import MagicMock
from tibanna.core import API


def _setup(mocker):
    mock_s3 = MagicMock()
    mocker.patch('tibanna.core.boto3.client', return_value=mock_s3)
    mocker.patch.object(API, 'IAM', new=MagicMock())
    return mock_s3


def test_setup_tibanna_env_retains_public_access_block_by_default(mocker):
    """K1/R8 regression: a fresh setup_tibanna_env call must retain S3 Block
    Public Access on the given buckets - it must not delete the block unless
    the operator explicitly opts in.
    """
    mock_s3 = _setup(mocker)

    API().setup_tibanna_env(buckets='somebucket,otherbucket', usergroup_tag='default')

    mock_s3.delete_public_access_block.assert_not_called()


def test_setup_tibanna_env_deletes_public_access_block_only_with_explicit_optin(mocker):
    mock_s3 = _setup(mocker)

    API().setup_tibanna_env(buckets='somebucket,otherbucket', usergroup_tag='default',
                            do_not_delete_public_access_block=False)

    assert mock_s3.delete_public_access_block.call_count == 2


def test_deploy_unicorn_cli_handler_retains_block_by_default(mocker):
    """The CLI handler must translate the new -Q/--enable-public-access-block-deletion
    opt-in flag into do_not_delete_public_access_block=True by default."""
    from tibanna import __main__ as main_module
    mock_api_instance = MagicMock()
    mocker.patch.object(main_module, 'API', return_value=mock_api_instance)

    main_module.deploy_unicorn(buckets='somebucket')

    _, kwargs = mock_api_instance.deploy_unicorn.call_args
    assert kwargs['do_not_delete_public_access_block'] is True


def test_deploy_unicorn_cli_handler_honors_explicit_optin(mocker):
    from tibanna import __main__ as main_module
    mock_api_instance = MagicMock()
    mocker.patch.object(main_module, 'API', return_value=mock_api_instance)

    main_module.deploy_unicorn(buckets='somebucket', enable_public_access_block_deletion=True)

    _, kwargs = mock_api_instance.deploy_unicorn.call_args
    assert kwargs['do_not_delete_public_access_block'] is False
