import pytest
from check_md5 import filechecker


def test_get_access_keys_live():
    # this test is live to s3, will potentially reveal secret info
    import os
    if os.environ.get("SECRET"):
        # run the test only if key set
        res = filechecker.get_access_keys()
        assert len(res.keys()) == 3
        assert res['secret']
        assert res['key']
        assert res['server']
