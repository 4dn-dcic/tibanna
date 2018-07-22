import boto3
import json
import random


def generate_policy_prefix(user_group_name):
    '''policy prefix for user group'''
    # add rangom tag to avoid attempting to overwrite a previously created and deleted policy and silently failing.
    random_tag = str(int(random.random() * 10000))
    tibanna_policy_prefix = 'tibanna_' + user_group_name + '_' + random_tag
    return tibanna_policy_prefix


def generate_policy_list_instanceprofiles():
    policy_list_instanceprofiles = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "Stmt1478801433000",
                "Effect": "Allow",
                "Action": [
                    "iam:ListInstanceProfiles"
                ],
                "Resource": [
                    "*"
                ]
            }
        ]
    }
    return policy_list_instanceprofiles


def generate_policy_cloudwatchlogs():
    policy_cloudwatchlogs = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*",
                "Effect": "Allow"
            }
        ]
    }
    return policy_cloudwatchlogs


def generate_policy_bucket_access(bucket_names):
    resource_list_buckets = ["arn:aws:s3:::" + bn for bn in bucket_names]
    resource_list_objects = ["arn:aws:s3:::" + bn + "/*" for bn in bucket_names]
    policy_bucket_access = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:ListBucket"
                ],
                "Resource": resource_list_buckets
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:DeleteObject"
                ],
                "Resource": resource_list_objects
            }
        ]
    }
    return policy_bucket_access


def generate_policy_iam_passrole_s3(account_id, tibanna_policy_prefix):
    role_resource = ['arn:aws:iam::' + account_id + ':role/' + tibanna_policy_prefix + '_s3']
    policy_iam_passrole_s3 = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "Stmt1478801396000",
                "Effect": "Allow",
                "Action": [
                    "iam:PassRole"
                ],
                "Resource": role_resource
            }
        ]
    }
    return policy_iam_passrole_s3


def generate_lambdainvoke_policy(account_id, region, tibanna_policy_prefix):
    function_arn_prefix = 'arn:aws:lambda:' + region + ':' + account_id + ':function/'
    resource = [function_arn_prefix + 'run_task_awsem' + '_' + tibanna_policy_prefix,
                function_arn_prefix + 'check_task_awsem' + '_' + tibanna_policy_prefix]
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": resource
            }
        ]
    }
    return policy


def generate_desc_stepfunction_policy(account_id, region, tibanna_policy_prefix):
    execution_arn_prefix = 'arn:aws:states:' + region + ':' + account_id + ':execution:'
    usergroup = tibanna_policy_prefix.replace('tibanna_', '')
    resource = execution_arn_prefix + '*' + usergroup + ':*'
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "states:DescribeExecution"
                ],
                "Resource": resource
            }
        ]
    }
    return policy


def generate_assume_role_policy_document(service):
    '''service: 'ec2', 'lambda' or 'states' '''
    AssumeRolePolicyDocument = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": service + ".amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    return AssumeRolePolicyDocument


def get_bucket_role_name(tibanna_policy_prefix):
    return tibanna_policy_prefix + '_s3'


def get_lambda_role_name(tibanna_policy_prefix, lambda_name):
    return tibanna_policy_prefix + '_' + lambda_name


def get_stepfunction_role_name(tibanna_policy_prefix):
    return tibanna_policy_prefix + '_states'


def create_empty_role_for_lambda(iam, verbose=False):
    client = iam.meta.client
    role_policy_doc_lambda = generate_assume_role_policy_document('lambda')
    empty_role_name = 'tibanna_lambda_init_role'
    try:
        client.get_role(RoleName=empty_role_name)
    except Exception:
        print("creating %s", empty_role_name)
        response = client.create_role(
           RoleName=empty_role_name,
           AssumeRolePolicyDocument=json.dumps(role_policy_doc_lambda)
        )
    if verbose:
        print(response)


def create_role_for_bucket(iam, tibanna_policy_prefix, account_id,
                           bucket_policy_name, verbose=False):
    client = iam.meta.client
    bucket_role_name = get_bucket_role_name(tibanna_policy_prefix)
    role_policy_doc_ec2 = generate_assume_role_policy_document('ec2')
    response = client.create_role(
        RoleName=bucket_role_name,
        AssumeRolePolicyDocument=json.dumps(role_policy_doc_ec2)
    )
    if verbose:
        print(response)
    role_bucket = iam.Role(bucket_role_name)
    response = role_bucket.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + bucket_policy_name
    )
    if verbose:
        print(response)


def create_role_for_run_task_awsem(iam, tibanna_policy_prefix, account_id,
                                   cloudwatch_policy_name, bucket_policy_name,
                                   list_policy_name, passrole_policy_name,
                                   desc_stepfunction_policy_name,
                                   verbose=False):
    client = iam.meta.client
    lambda_run_role_name = get_lambda_role_name(tibanna_policy_prefix, 'run_task_awsem')
    role_policy_doc_lambda = generate_assume_role_policy_document('lambda')
    response = client.create_role(
        RoleName=lambda_run_role_name,
        AssumeRolePolicyDocument=json.dumps(role_policy_doc_lambda)
    )
    role_lambda_run = iam.Role(lambda_run_role_name)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + list_policy_name
    )
    if verbose:
        print(response)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + cloudwatch_policy_name
    )
    if verbose:
        print(response)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + passrole_policy_name
    )
    if verbose:
        print(response)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + bucket_policy_name
    )
    if verbose:
        print(response)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::aws:policy/AmazonEC2FullAccess'
    )
    if verbose:
        print(response)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + desc_stepfunction_policy_name
    )
    if verbose:
        print(response)


def create_role_for_check_task_awsem(iam, tibanna_policy_prefix, account_id,
                                     cloudwatch_policy_name, bucket_policy_name,
                                     verbose=False):
    client = iam.meta.client
    lambda_check_role_name = get_lambda_role_name(tibanna_policy_prefix, 'check_task_awsem')
    role_policy_doc_lambda = generate_assume_role_policy_document('lambda')
    response = client.create_role(
        RoleName=lambda_check_role_name,
        AssumeRolePolicyDocument=json.dumps(role_policy_doc_lambda)
    )
    if verbose:
        print(response)
    role_lambda_run = iam.Role(lambda_check_role_name)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + cloudwatch_policy_name
    )
    if verbose:
        print(response)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + bucket_policy_name
    )
    if verbose:
        print(response)


def create_role_for_stepfunction(iam, tibanna_policy_prefix, account_id,
                                 lambdainvoke_policy_name, verbose=False):
    client = iam.meta.client
    stepfunction_role_name = get_stepfunction_role_name(tibanna_policy_prefix)
    role_policy_doc = generate_assume_role_policy_document('states')
    response = client.create_role(
        RoleName=stepfunction_role_name,
        AssumeRolePolicyDocument=json.dumps(role_policy_doc)
    )
    if verbose:
        print(response)
    role_stepfunction = iam.Role(stepfunction_role_name)
    response = role_stepfunction.attach_policy(
        PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaRole'
        # PolicyArn='arn:aws:iam::' + account_id + ':policy/' + lambdainvoke_policy_name
    )
    if verbose:
        print(response)


def create_user_group(iam, group_name, bucket_policy_name, account_id, verbose=False):
    client = iam.meta.client
    response = client.create_group(
        GroupName=group_name
    )
    if verbose:
        print(response)
    group = iam.Group(group_name)
    response = group.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + bucket_policy_name
    )
    if verbose:
        print(response)
    response = group.attach_policy(
        PolicyArn='arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess'
    )
    if verbose:
        print(response)
    response = group.attach_policy(
        PolicyArn='arn:aws:iam::aws:policy/AWSStepFunctionsConsoleFullAccess'
    )
    if verbose:
        print(response)
    response = group.attach_policy(
        PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
    )
    if verbose:
        print(response)


def create_tibanna_iam(account_id, bucket_names, user_group_name, region, verbose=False):
    """creates IAM policies and roles and a user group for tibanna
    returns prefix of all IAM policies, roles and group.
    Total 4 policies, 3 roles and 1 group is generated that is associated with a single user group
    A user group shares permission for buckets, tibanna execution and logs
    """
    # create prefix that represent a single user group
    tibanna_policy_prefix = generate_policy_prefix(user_group_name)
    iam = boto3.resource('iam')
    client = iam.meta.client
    # bucket policy
    bucket_policy_name = tibanna_policy_prefix + '_bucket_access'
    policy_ba = generate_policy_bucket_access(bucket_names)
    response = client.create_policy(
        PolicyName=bucket_policy_name,
        PolicyDocument=json.dumps(policy_ba),
    )
    # lambda policies
    # list_instanceprofiles : by default not user-dependent,
    # but create per user group to allow future modification per user-group
    list_policy_name = tibanna_policy_prefix + '_list_instanceprofiles'
    response = client.create_policy(
        PolicyName=list_policy_name,
        PolicyDocument=json.dumps(generate_policy_list_instanceprofiles()),
    )
    if verbose:
        print(response)
    # cloudwatchlogs: by default not user-dependent,
    # but create per user group to allow future modification per user-group
    cloudwatch_policy_name = tibanna_policy_prefix + '_cloudwatchlogs'
    response = client.create_policy(
        PolicyName=cloudwatch_policy_name,
        PolicyDocument=json.dumps(generate_policy_cloudwatchlogs()),
    )
    if verbose:
        print(response)
    # iam_passrole_s3: passrole policy per user group
    passrole_policy_name = tibanna_policy_prefix + '_iam_passrole_s3'
    policy_iam_ps3 = generate_policy_iam_passrole_s3(account_id, tibanna_policy_prefix)
    response = client.create_policy(
        PolicyName=passrole_policy_name,
        PolicyDocument=json.dumps(policy_iam_ps3),
    )
    if verbose:
        print(response)
    # lambdainvoke policy for step function
    lambdainvoke_policy_name = tibanna_policy_prefix + '_lambdainvoke'
    policy_lambdainvoke = generate_lambdainvoke_policy(account_id, region, tibanna_policy_prefix)
    response = client.create_policy(
        PolicyName=lambdainvoke_policy_name,
        PolicyDocument=json.dumps(policy_lambdainvoke),
    )
    if verbose:
        print(response)
    desc_stepfunction_policy_name = tibanna_policy_prefix + '_desc_sts'
    policy_desc_stepfunction = generate_desc_stepfunction_policy(account_id, region, tibanna_policy_prefix)
    response = client.create_policy(
        PolicyName=desc_stepfunction_policy_name,
        PolicyDocument=json.dumps(policy_desc_stepfunction),
    )
    if verbose:
        print(response)
    # roles
    # role for bucket
    create_role_for_bucket(iam, tibanna_policy_prefix, account_id, bucket_policy_name)
    # role for lambda
    create_role_for_run_task_awsem(iam, tibanna_policy_prefix, account_id,
                                   cloudwatch_policy_name, bucket_policy_name,
                                   list_policy_name, passrole_policy_name,
                                   desc_stepfunction_policy_name)
    create_role_for_check_task_awsem(iam, tibanna_policy_prefix, account_id,
                                     cloudwatch_policy_name, bucket_policy_name)
    create_empty_role_for_lambda(iam)
    # role for step function
    create_role_for_stepfunction(iam, tibanna_policy_prefix, account_id, lambdainvoke_policy_name)
    # instance profile
    instance_profile_name = get_bucket_role_name(tibanna_policy_prefix)
    client.create_instance_profile(
        InstanceProfileName=instance_profile_name
    )
    ip = iam.InstanceProfile(instance_profile_name)
    ip.add_role(
        RoleName=instance_profile_name
    )
    # create IAM group for users who share permission
    create_user_group(iam, tibanna_policy_prefix, bucket_policy_name, account_id)
    return tibanna_policy_prefix
