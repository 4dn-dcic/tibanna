from fnmatch import fnmatchcase

from tibanna.iam_utils import IAM
from tibanna.stepfunction import StepFunctionUnicorn


def _iam():
    return IAM('default', ['mybucket'], no_randomize=True)


def test_run_task_does_not_get_full_ec2_access():
    """C1 regression: run_task must not carry AmazonEC2FullAccess (full
    control over all EC2 in the account). It should only get the scoped
    ec2_launch policy (RunInstances/CreateFleet/CreateLaunchTemplate/
    DeleteLaunchTemplate/DeleteFleets/Describe*).
    """
    iam = _iam()
    arns = iam.policy_arn_list_for_role[iam.run_task_lambda_name]
    assert not any('AmazonEC2FullAccess' in arn for arn in arns)
    assert any(arn.endswith('_ec2_launch') for arn in arns)


def test_ec2_launch_policy_has_no_wildcard_ec2_full_access_actions():
    """The custom ec2_launch policy must be an explicit action allowlist,
    not a wildcard ec2:* grant, and must cover what run_task actually calls
    (create_fleet/create_launch_template/delete_fleets/delete_launch_template/
    describe_instances/describe_instance_types in ec2_utils.py)."""
    iam = _iam()
    policy = iam.policy_ec2_launch
    actions = policy['Statement'][0]['Action']
    assert 'ec2:*' not in actions
    required = {
        'ec2:RunInstances', 'ec2:CreateFleet', 'ec2:CreateLaunchTemplate',
        'ec2:DeleteLaunchTemplate', 'ec2:DeleteFleets',
        'ec2:DescribeInstances', 'ec2:DescribeInstanceTypes',
    }
    assert required.issubset(set(actions))
    assert 'ec2:TerminateInstances' not in actions


def test_terminate_instances_policy_scoped_to_awsem_tag():
    """C1 regression: ec2:TerminateInstances must be conditioned on the
    Type=awsem tag Tibanna applies to instances it launches (ec2_utils.py),
    not granted on Resource: '*' with no condition.
    """
    iam = _iam()
    statement = iam.policy_terminate_instances['Statement'][0]
    assert statement['Action'] == 'ec2:TerminateInstances'
    condition = statement.get('Condition', {})
    assert condition.get('StringEquals', {}).get('ec2:ResourceTag/Type') == 'awsem'


def test_stepfunction_role_uses_scoped_lambdainvoke_not_wildcard():
    """C10 regression: the step-function role must use the scoped
    lambdainvoke custom policy (restricted to the three tibanna lambdas),
    not the AWSLambdaRole managed policy which grants lambda:InvokeFunction
    on Resource: '*'.
    """
    iam = _iam()
    arns = iam.policy_arn_list_for_role['stepfunction']
    assert not any('AWSLambdaRole' in arn for arn in arns)
    assert any(arn.endswith('_lambdainvoke') for arn in arns)


def test_lambdainvoke_policy_scoped_to_tibanna_lambdas_only():
    """Deployed lambdas are named '<lambda_name>_<usergroup>[_<dev_suffix>]'
    (core.py deploy_lambda / utils.create_tibanna_suffix), NOT
    '<lambda_name>_<tibanna_policy_prefix>'. The policy must grant exactly
    those names (plus the dev-suffix wildcard), or Step Functions gets
    AccessDenied on every invocation once AWSLambdaRole is gone.
    """
    iam = _iam()
    policy = iam.policy_lambdainvoke
    statement = policy['Statement'][0]
    assert statement['Action'] == ['lambda:InvokeFunction']
    resources = statement['Resource']
    assert resources != '*'
    expected_prefix = 'arn:aws:lambda:%s:%s:function:' % (iam.region, iam.account_id)
    expected = []
    for name in iam.lambda_names:
        expected.extend([expected_prefix + name + '_' + iam.user_group_name,
                         expected_prefix + name + '_' + iam.user_group_name + '_*'])
    assert resources == expected
    assert all(':function/' not in resource for resource in resources)
    # the misnamed 'tibanna_'-prefixed variant must not come back
    assert all('_' + iam.tibanna_policy_prefix not in resource for resource in resources)


def test_lambdainvoke_policy_covers_stepfunction_invoked_arns():
    """Cross-check the policy against the actual state-machine definition:
    every lambda ARN StepFunctionUnicorn invokes (with and without a dev
    suffix) must be covered by the lambdainvoke policy resources.
    """
    iam = _iam()
    resources = iam.policy_lambdainvoke['Statement'][0]['Resource']

    def covered(arn):
        return any(fnmatchcase(arn, pattern) for pattern in resources)

    for dev_suffix in (None, 'dev'):
        sfn = StepFunctionUnicorn(dev_suffix=dev_suffix, usergroup=iam.user_group_name)
        for state in ('RunTaskAwsem', 'CheckTaskAwsem'):
            invoked_arn = sfn.sfn_state_defs[state]['Resource']
            assert covered(invoked_arn), invoked_arn


def test_ec2_launch_policy_type_is_created_and_cleaned_up():
    """The new policy type must be part of the standard create/cleanup
    lifecycle (policy_types), not a one-off definition nobody provisions."""
    iam = _iam()
    assert 'ec2_launch' in iam.policy_types
    # policy_name/policy_definition must resolve without raising
    name = iam.policy_name('ec2_launch')
    assert name.endswith('_ec2_launch')
    assert iam.policy_definition('ec2_launch') == iam.policy_ec2_launch
