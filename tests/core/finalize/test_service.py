from core.finalize.service import handler
from core import ff_utils
import pytest
from ..conftest import valid_env
import json
import mock


@valid_env
@pytest.mark.webtest
def test_finalize(finalize_event_data, tibanna_env, ff_keys):
    # wfrun = ff_utils.get_metadata("/search/?type=WorkflowRun&limit=1", ff_keys)['@graph'][0]
    finalize_event_data.update(tibanna_env)

    with mock.patch.object(ff_utils.WorkflowRunMetadata, "post") as post2ff:
        ret = handler(finalize_event_data, None)
        post2ff.assert_called_once()
        assert json.dumps(ret)
