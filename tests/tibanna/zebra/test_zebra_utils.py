from tibanna_ffcommon.portal_utils import (
    TibannaSettings,
    FormatExtensionMap,
)
from tibanna_cgap.zebra_utils import (
    WorkflowRunMetadata,
    ProcessedFileMetadata,
    FourfrontStarter
)
import pytest
from tests.tibanna.zebra.conftest import valid_env
from tibanna.utils import printlog
import mock


@valid_env
def test_tibanna():
    data = {'env': 'fourfront-cgap',
            'settings': {'1': '1'}}
    tibanna = TibannaSettings(**data)
    assert tibanna
    assert tibanna.as_dict() == data


@valid_env
def test_format_extension_map():
    data = {'env': 'fourfront-cgap',
            'settings': {'1': '1'}}
    tibanna = TibannaSettings(**data)
    fe_map = FormatExtensionMap(tibanna.ff_keys)
    assert(fe_map)
    assert 'bwt' in fe_map.fe_dict.keys()


@valid_env
def test_fourfront_starter(start_run_event_md5):
    starter = FourfrontStarter(**start_run_event_md5)
    assert starter
    assert 'arguments' in starter.inp.wf_meta
    assert len(starter.inp.wf_meta['arguments']) == 2
    assert starter.inp.wf_meta['arguments'][1]['argument_type'] == 'Output report file'
    starter.run()
    assert len(starter.output_argnames) == 1


@valid_env
def test_fourfront_starter2(start_run_event_bwa_check):
    starter = FourfrontStarter(**start_run_event_bwa_check)
    assert starter
    assert not starter.user_supplied_output_files('raw_bam')
    assert len(starter.output_argnames) == 2
    assert starter.output_argnames[0] == 'raw_bam'
    assert starter.arg('raw_bam')['argument_type'] == 'Output processed file'
    assert starter.pf('raw_bam')
    starter.create_pfs()
    assert len(starter.pfs) == 1
