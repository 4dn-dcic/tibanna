"""C4: the audit found that `retry_without_spot` flips cfg.spot_instance to
False and retries create_fleet, but never recreates the launch template - so
the retry's launch template still declares InstanceMarketOptions=spot even
though the fleet request itself now asks for on-demand target capacity.

Whether that combination makes EC2 Fleet honor the spot market option, the
on-demand target capacity, or reject the request outright is a live AWS
service-precedence question this test cannot answer (see K3 in the Sol
delta report) - it is intentionally NOT exercised here. This test only
captures and asserts the exact shape of the second (retry) request and the
launch template's state, which is what a live contract test would need to
send to get a real answer.
"""
from unittest.mock import MagicMock
from tibanna.ec2_utils import Execution
from tibanna.utils import create_jobid


def _build_execution(mocker, ec2_mock):
    mocker.patch('tibanna.ec2_utils.boto3.client', return_value=ec2_mock)
    input_dict = {
        'args': {'output_S3_bucket': 'somebucket', 'cwl_main_filename': 'md5.cwl', 'cwl_directory_url': 'someurl'},
        'config': {'log_bucket': 'tibanna-output', 'instance_type': 't3.micro',
                   'spot_instance': True, 'behavior_on_capacity_limit': 'retry_without_spot'},
        'jobid': create_jobid(),
    }
    return Execution(input_dict, dryrun=True)


def test_retry_without_spot_second_request_shape(mocker):
    ec2_mock = MagicMock()
    ec2_mock.describe_instance_types.return_value = {
        'InstanceTypes': [{
            'InstanceType': 't3.micro',
            'EbsInfo': {'EbsOptimizedSupport': 'default'},
            'ProcessorInfo': {'SupportedArchitectures': ['x86_64']},
        }]
    }
    ec2_mock.create_fleet.side_effect = [
        {
            'FleetId': 'fid1',
            'Instances': [],
            'Errors': [{'ErrorCode': 'InsufficientInstanceCapacity', 'ErrorMessage': 'no spot capacity'}],
        },
        {
            'FleetId': 'fid2',
            'Instances': [{'InstanceIds': ['i-0123456789abcdef0']}],
        },
    ]
    ec2_mock.delete_fleets.return_value = {}
    ec2_mock.create_launch_template.return_value = {}
    ec2_mock.delete_launch_template.return_value = {}

    execution = _build_execution(mocker, ec2_mock)
    execution.userdata = execution.create_userdata()
    instance_id = execution.launch_and_get_instance_id()

    assert instance_id == 'i-0123456789abcdef0'
    assert ec2_mock.create_fleet.call_count == 2

    first_request = ec2_mock.create_fleet.call_args_list[0].kwargs
    second_request = ec2_mock.create_fleet.call_args_list[1].kwargs

    # The Python-level flag change is real: the retry does ask for on-demand
    # target capacity...
    assert first_request['TargetCapacitySpecification']['DefaultTargetCapacityType'] == 'spot'
    assert second_request['TargetCapacitySpecification']['DefaultTargetCapacityType'] == 'on-demand'

    # ...but both requests reference the SAME launch template by name/version
    # (create_launch_template is called exactly once, before the retry loop),
    # and that template was built while cfg.spot_instance was still True.
    assert first_request['LaunchTemplateConfigs'][0]['LaunchTemplateSpecification'] == \
        second_request['LaunchTemplateConfigs'][0]['LaunchTemplateSpecification']
    assert ec2_mock.create_launch_template.call_count == 1
    launch_template_data = ec2_mock.create_launch_template.call_args.kwargs['LaunchTemplateData']
    assert launch_template_data.get('InstanceMarketOptions', {}).get('MarketType') == 'spot'

    # This is exactly the ambiguous combination flagged by C4/K3: an
    # on-demand fleet request (second_request above) pointed at a launch
    # template that still declares spot market options. Whether EC2 Fleet
    # honors the fleet-level on-demand target capacity or the stale
    # template-level spot option is a live AWS precedence question - see
    # test_retry_without_spot_live_contract_TODO below.


def test_retry_without_spot_live_contract_TODO():
    """Documented, intentionally-not-run placeholder for the live AWS
    contract test K3 calls for.

    This does not run in CI and makes no AWS calls. Before treating C4 as a
    confirmed operational break (or closing it as a false positive), someone
    with an isolated AWS test account should:
      1. Create a launch template with InstanceMarketOptions={'MarketType': 'spot', ...}
         (mirroring create_launch_template() above).
      2. Call ec2:CreateFleet with that launch template and
         TargetCapacitySpecification.DefaultTargetCapacityType='on-demand',
         Type='instant', TotalTargetCapacity=1, using the smallest allowed
         instance type.
      3. Record whether the returned instance is spot or on-demand (or the
         call errors), then delete the fleet and launch template immediately.
      4. If AWS honors the stale spot option (or errors), fix
         launch_and_get_instance_id() to delete_launch_template() and
         create_launch_template() again after flipping cfg.spot_instance,
         inside the retry_without_spot branch, before the next create_fleet()
         call - and extend the request-shape test above to assert the second
         request's LaunchTemplateSpecification differs from the first's.
      5. If AWS's target capacity type overrides the launch template, close
         C4 as a false positive (but consider simplifying the launch
         template so it doesn't carry a self-contradictory configuration).
    """
    pass
