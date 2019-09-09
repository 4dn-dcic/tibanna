from tibanna_4dn.pony_utils import (
    FourfrontStarter,
)
import pytest
from tests.tibanna.pony.conftest import valid_env


@valid_env
def test_fourfront_starter(start_run_md5_data):
    starter = FourfrontStarter(**start_run_md5_data)
    assert starter
    assert 'arguments' in starter.inp.wf_meta
    assert len(starter.inp.wf_meta['arguments']) == 2
    assert starter.inp.wf_meta['arguments'][1]['argument_type'] == 'Output report file'
    starter.run()
    assert len(starter.output_argnames) == 1


@valid_env
def test_fourfront_starter2(start_run_nestedarray_data):
    starter = FourfrontStarter(**start_run_nestedarray_data)
    assert starter
    starter.run()
    assert len(starter.inp.args.input_files['input_file']['object_key']) == 2
    assert len(starter.inp.args.input_files['input_file']['object_key'][0]) == 2


@valid_env
def test_fourfront_starter3(start_run_dependency_data):
    starter = FourfrontStarter(**start_run_dependency_data)
    assert starter
    starter.run()
    assert starter.inp.dependency


@valid_env
def test_fourfront_starter4(start_run_dependency_fail_data):
    starter = FourfrontStarter(**start_run_dependency_fail_data)
    assert starter
    starter.run()
    assert starter.inp.dependency


@valid_env
def test_fourfront_starter5(start_run_fail_data):
    starter = FourfrontStarter(**start_run_fail_data)
    assert starter
    starter.run()


@valid_env
def test_fourfront_starter6(start_run_fixedname_data):
    starter = FourfrontStarter(**start_run_fixedname_data)
    assert starter
    starter.run()
    assert starter.inp.as_dict().get('_tibanna').get('run_name') == 'md5_test'


@valid_env
def test_fourfront_starter7(start_run_hicprocessingbam_customfield_wALL_data):
    starter = FourfrontStarter(**start_run_hicprocessingbam_customfield_wALL_data)
    assert starter
    starter.run()


@valid_env
def test_fourfront_starter8(start_run_hicprocessingbam_customfield_wArgname_data):
    starter = FourfrontStarter(**start_run_hicprocessingbam_customfield_wArgname_data)
    assert starter
    starter.run()


@valid_env
def test_fourfront_starter9(start_run_hicprocessingpartb_data):
    starter = FourfrontStarter(**start_run_hicprocessingpartb_data)
    assert starter
    starter.run()
