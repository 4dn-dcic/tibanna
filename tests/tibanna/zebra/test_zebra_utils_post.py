from tibanna_ffcommon.portal_utils import (
    TibannaSettings,
    FormatExtensionMap,
)
from tibanna_cgap.zebra_utils import (
    FourfrontStarter
)
import pytest
from tests.tibanna.zebra.conftest import valid_env


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
def test_qc_list_updater(update_meta
