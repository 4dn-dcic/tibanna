from core import utils


def test_get_access_keys_live():
    # this test is live to s3, will potentially reveal secret info
    import os
    if os.environ.get("SECRET"):
        # run the test only if key set
        res = utils.get_access_keys()
        assert len(res.keys()) == 3
        assert res['secret']
        assert res['key']
        assert res['server']


def test_get_sbg_keys_live():
    # this test is live to s3, will potentially reveal secret info
    import os
    if os.environ.get("SECRET"):
        # run the test only if key set
        res = utils.get_sbg_keys()
        assert res


def test_get_s3_keys_live():
    # this test is live to s3, will potentially reveal secret info
    import os
    if os.environ.get("SECRET"):
        # run the test only if key set
        res = utils.get_s3_keys()
        assert len(res.keys()) == 2
        assert res['secret']
        assert res['key']
