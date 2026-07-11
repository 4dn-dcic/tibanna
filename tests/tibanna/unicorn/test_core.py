from datetime import datetime, timezone
from unittest.mock import MagicMock
from tibanna.core import API


def _exc(name, stop_date):
    return {'executionArn': name, 'stopDate': stop_date}


def test_rerun_many_paginates_beyond_first_page(mocker):
    """C3 regression: rerun_many must not silently stop at the first
    (<=100-result) page of list_executions - it should follow every page
    returned by the paginator and rerun every match.
    """
    old_stop = datetime(2018, 1, 1, tzinfo=timezone.utc)
    new_stop = datetime(2020, 1, 1, tzinfo=timezone.utc)
    page1 = {'executions': [_exc('exec-page1-old', old_stop), _exc('exec-page1-new', new_stop)]}
    page2 = {'executions': [_exc('exec-page2-new', new_stop)]}

    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [page1, page2]
    mock_client = MagicMock()
    mock_client.get_paginator.return_value = mock_paginator
    mocker.patch('tibanna.core.boto3.client', return_value=mock_client)

    api = API()
    mock_rerun = mocker.patch.object(api, 'rerun')
    mocker.patch('tibanna.core.time.sleep')

    reran = api.rerun_many(sfn='tibanna_unicorn_test', stopdate='01Jan2019', stophour=0, stopminute=0,
                           sleeptime=0)

    assert reran == 2
    assert mock_rerun.call_count == 2
    reran_execs = {call.args[0] for call in mock_rerun.call_args_list}
    assert reran_execs == {'exec-page1-new', 'exec-page2-new'}
    mock_client.get_paginator.assert_called_once_with('list_executions')


def test_list_sfns_uses_requested_sfn_type(mocker):
    """C16 regression: list_sfns must actually filter by the sfn_type argument
    instead of silently ignoring it and always using the class default.
    """
    mock_client = MagicMock()
    mock_client.list_state_machines.return_value = {
        'stateMachines': [
            {'name': 'tibanna_unicorn_test', 'creationDate': datetime(2020, 1, 1), 'stateMachineArn': 'arn1'},
            {'name': 'tibanna_pony_test', 'creationDate': datetime(2020, 1, 1), 'stateMachineArn': 'arn2'},
        ]
    }
    mocker.patch('tibanna.core.boto3.client', return_value=mock_client)

    api = API()
    printed = []
    mocker.patch('builtins.print', side_effect=lambda line: printed.append(line))
    api.list_sfns(sfn_type='pony')

    assert any('tibanna_pony_test' in line for line in printed)
    assert not any('tibanna_unicorn_test' in line for line in printed)
