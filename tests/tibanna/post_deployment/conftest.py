import os
from tibanna.core import API

REGION1 = 'us-east-1'
REGION2 = 'us-west-1'

DEV_SUFFIX = 'pre'
DEV_GROUP_SUFFIX = 'testgroup'
DEV_SFN_REGION1 = 'tibanna_unicorn_' + DEV_GROUP_SUFFIX + '1' + '_' + DEV_SUFFIX  # deployed to us-east-1
DEV_SFN_REGION2 = 'tibanna_unicorn_' + DEV_GROUP_SUFFIX + '1' + '_' + DEV_SUFFIX  # deployed to us-west-1
DEV_SFN2_REGION2 = 'tibanna_unicorn_' + DEV_GROUP_SUFFIX + '2' + '_' + DEV_SUFFIX  # deployed to us-west-1


def get_test_json(file_name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    event_file_name = os.path.join(dir_path, 'test_json', file_name)
    return event_file_name


def deploy_sfn1_to_region1():
    os.environ['AWS_DEFAULT_REGION'] = REGION1
    API().deploy_unicorn(suffix=DEV_SUFFIX, buckets='tibanna-output,soos-4dn-bucket', usergroup=DEV_GROUP_SUFFIX + '1')


def deploy_sfn1_to_region2():
    os.environ['AWS_DEFAULT_REGION'] = REGION2
    API().deploy_unicorn(suffix=DEV_SUFFIX, buckets='tibanna-output,soos-4dn-bucket', usergroup=DEV_GROUP_SUFFIX + '1')


def deploy_sfn2_to_region2():
    os.environ['AWS_DEFAULT_REGION'] = REGION2
    buckets = 'tibanna-output,elasticbeanstalk-fourfront-webdev-files,soos-4dn-bucket'
    API().deploy_unicorn(suffix=DEV_SUFFIX, buckets=buckets, usergroup=DEV_GROUP_SUFFIX + '2')


def cleanup_sfn1_region1():
    os.environ['AWS_DEFAULT_REGION'] = REGION1
    API().cleanup(user_group_name=DEV_GROUP_SUFFIX + '1', suffix=DEV_SUFFIX)


def cleanup_sfn1_region2():
    os.environ['AWS_DEFAULT_REGION'] = REGION2
    API().cleanup(user_group_name=DEV_GROUP_SUFFIX + '1', suffix=DEV_SUFFIX)


def cleanup_sfn2_region2():
    os.environ['AWS_DEFAULT_REGION'] = REGION2
    API().cleanup(user_group_name=DEV_GROUP_SUFFIX + '2', suffix=DEV_SUFFIX)


def pytest_sessionstart(session):
    deploy_sfn1_to_region1()
    deploy_sfn1_to_region2()
    deploy_sfn2_to_region2()


def pytest_sessionfinish(session, exitstatus):
    cleanup_sfn1_region1()
    cleanup_sfn1_region2()
    cleanup_sfn2_region2()
