import base64
import hashlib
import os
from unittest.mock import MagicMock
from tibanna.ec2_utils import Execution
from tibanna.vars import TIBANNA_AWSF_ASSET_COMMIT, TIBANNA_REPO_BRANCH
from tibanna.awsf3_checksums import (
    AWS_RUN_WORKFLOW_GENERIC_SHA256,
    CLOUDWATCH_AGENT_CONFIG_SHA256,
    SPOT_FAILURE_DETECTION_SHA256,
)

AWSF3_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', '..', 'awsf3')


def _sha256_of(filename):
    with open(os.path.join(AWSF3_DIR, filename), 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_pinned_checksums_match_the_actual_awsf3_files():
    """D1 drift guard: awsf3_checksums.py must always reflect the current
    bytes of the fetched assets. If this fails, a source change to one of
    the three files was made without updating the corresponding pinned
    checksum - update tibanna/awsf3_checksums.py as part of that change.
    """
    assert AWS_RUN_WORKFLOW_GENERIC_SHA256 == _sha256_of('aws_run_workflow_generic.sh')
    assert CLOUDWATCH_AGENT_CONFIG_SHA256 == _sha256_of('cloudwatch_agent_config.json')
    assert SPOT_FAILURE_DETECTION_SHA256 == _sha256_of('spot_failure_detection.sh')


def test_verification_disabled_flag_is_propagated_to_run_task_lambda_env():
    """D1: TIBANNA_AWSF_SCRIPT_VERIFICATION_DISABLED must be threaded through
    to the run_task lambda's deployed environment (like TIBANNA_REPO_BRANCH
    already is), or setting it locally before `tibanna deploy_unicorn` would
    have no effect on the actual running Lambda.
    """
    from tibanna.core import API
    api = API()
    env = api.env_list(api.run_task_lambda)
    assert 'TIBANNA_AWSF_SCRIPT_VERIFICATION_DISABLED' in env


def test_default_repo_ref_is_reachable_immutable_asset_commit():
    """D1 regression: the default fetch location must not be a floating
    branch or a prospective tag that may not exist when source deployments
    run. It is pinned to the commit containing the checksummed assets.
    """
    assert TIBANNA_REPO_BRANCH == TIBANNA_AWSF_ASSET_COMMIT
    assert len(TIBANNA_AWSF_ASSET_COMMIT) == 40
    assert all(c in '0123456789abcdef' for c in TIBANNA_AWSF_ASSET_COMMIT)
    assert TIBANNA_REPO_BRANCH != 'master'


def _build_execution(mocker):
    mock_ec2 = MagicMock()
    mock_ec2.describe_instance_types.return_value = {
        'InstanceTypes': [{
            'InstanceType': 't3.micro',
            'EbsInfo': {'EbsOptimizedSupport': 'default'},
            'ProcessorInfo': {'SupportedArchitectures': ['x86_64']},
        }]
    }
    mocker.patch('tibanna.ec2_utils.boto3.client', return_value=mock_ec2)
    input_dict = {
        'args': {
            'input_files': {},
            'output_S3_bucket': 'somebucket',
            'app_name': 'md5',
            'cwl_main_filename': 'md5.cwl',
            'cwl_directory_url': 'someurl',
        },
        'config': {'log_bucket': 'somebucket', 'instance_type': 't3.micro', 'ebs_size': 20},
        'jobid': 'myjobid',
    }
    return Execution(input_dict)


def _decoded_userdata(execution, **kwargs):
    userdata = execution.create_userdata(**kwargs)
    return base64.b64decode(userdata.encode('ascii')).decode('ascii')


def test_userdata_contains_no_mutable_master_url(mocker):
    """D1 acceptance criterion: generated user-data must not fetch from a
    mutable branch or floating `latest` location."""
    execution = _build_execution(mocker)
    userdata_str = _decoded_userdata(execution)
    assert '/master/' not in userdata_str


def test_userdata_verifies_bootstrap_script_before_sourcing(mocker):
    """D1 acceptance criterion: bootstrap bytes must be tied to an immutable
    version and verified (sha256) before being made executable/sourced."""
    execution = _build_execution(mocker)
    userdata_str = _decoded_userdata(execution)

    assert 'RUN_SCRIPT_SHA256={}'.format(AWS_RUN_WORKFLOW_GENERIC_SHA256) in userdata_str
    assert 'CW_CONFIG_SHA256={}'.format(CLOUDWATCH_AGENT_CONFIG_SHA256) in userdata_str
    assert 'SPOT_SCRIPT_SHA256={}'.format(SPOT_FAILURE_DETECTION_SHA256) in userdata_str

    wget_idx = userdata_str.index('wget $SCRIPT_URL/$RUN_SCRIPT')
    verify_idx = userdata_str.index('sha256sum -c -')
    chmod_idx = userdata_str.index('chmod +x $RUN_SCRIPT')
    source_idx = userdata_str.index('source $RUN_SCRIPT')
    # verification must happen strictly between the download and execution
    assert wget_idx < verify_idx < chmod_idx < source_idx
    # a mismatch must fail closed: shut down and exit, not just log a warning
    verify_line = userdata_str[verify_idx:userdata_str.index('\n', verify_idx)]
    assert 'shutdown' in verify_line
    assert 'exit 1' in verify_line

    # the fetched-script URL/hashes are threaded into the inner script so it
    # can verify its own further downloads (cloudwatch config, spot script)
    assert '-u $SCRIPT_URL' in userdata_str
    assert '-w $CW_CONFIG_SHA256' in userdata_str
    assert '-z $SPOT_SCRIPT_SHA256' in userdata_str
    assert ' -x' not in userdata_str.split('source $RUN_SCRIPT', 1)[1].split('\n')[0]


def test_userdata_dev_override_disables_verification_only_when_set(mocker):
    """D1: the verification-disable dev override must be off by default and
    must never be silently enabled."""
    execution = _build_execution(mocker)
    userdata_str = _decoded_userdata(execution)
    assert 'sha256sum -c -' in userdata_str

    mocker.patch('tibanna.ec2_utils.TIBANNA_AWSF_SCRIPT_VERIFICATION_DISABLED', True)
    userdata_str_disabled = _decoded_userdata(execution)
    assert 'sha256sum -c -' not in userdata_str_disabled
    assert 'WARNING: bootstrap script sha256 verification disabled' in userdata_str_disabled
    assert ' -x' in userdata_str_disabled.split('source $RUN_SCRIPT', 1)[1].split('\n')[0]
