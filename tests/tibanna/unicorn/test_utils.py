from tibanna.exceptions import (
    exception_coordinator,
    StillRunningException,
    AWSEMJobErrorException,
)
import pytest
import mock


@exception_coordinator("wrapped_fun", mock.Mock(side_effect=StillRunningException("metadata")))
def wrapped_fun(event, context):
    raise StillRunningException("I should not be called")


# this will raise an error
@exception_coordinator("update_ffmeta_awsem", mock.Mock())
def update_ffmeta_error_fun(event, context):
    raise Exception("I should raise an error")


@exception_coordinator('error_fun', mock.Mock())
def error_fun(event, context):
    raise Exception("lambda made a mess")


@exception_coordinator('awsem_error_fun', mock.Mock())
def awsem_error_fun(event, context):
    raise AWSEMJobErrorException()


def test_exception_coordinator_errors_are_dumped_into_return_dict():
    res = error_fun({'some': 'data', 'push_error_to_end': True}, None)
    assert res['some'] == 'data'
    assert res['error']
    assert 'Error on step: error_fun' in res['error']


def test_exception_coordinator_throws_if_error_set_in_input_json():
    # only throw the error because lambda name is update_ffmeta_awsem
    with pytest.raises(Exception):
        event = {'error': 'same like skip', 'push_error_to_end': True}
        update_ffmeta_error_fun(event, None)


def test_exception_coordinator_error_thrown_if_ignored_exceptions():
    # throw an error because this is an ignored exception and
    # no 'error' in event json
    with pytest.raises(Exception):
        wrapped_fun({}, None)


def test_exception_coordinator_error_propogates():
    # skip throwing an error because 'error' is in event json and the
    # lambda name != update_ffmeta_awsem. error is propagated to the res
    # and will be returned exactly as input
    res = wrapped_fun({'error': 'should not raise', 'push_error_to_end': True}, None)
    assert res['error'] == 'should not raise'


def test_exception_coordinator_skips_when_appropriate():
    wrapped_fun({'skip': 'wrapped_fun'}, None)


def test_exception_coordinator_skips_in_list():
    wrapped_fun({'skip': ['wrapped_fun', 'fun2']}, None)


def test_exception_coordinator_normally_doesnt_skip():
    with pytest.raises(StillRunningException) as exec_nfo:
        wrapped_fun({'skip': 'somebody_else'}, None)
    assert exec_nfo
    assert 'should not be called' in str(exec_nfo.value)


def test_exception_coordinator_calls_metadata_only_func():
    with pytest.raises(StillRunningException) as exec_nfo:
        wrapped_fun({'skip': 'somebody_else', 'metadata_only': 'wrapped_fun'}, None)

    assert exec_nfo
    assert 'metadata' in str(exec_nfo.value)
