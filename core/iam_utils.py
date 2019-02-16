import boto3
import json
import random


def generate_policy_prefix(user_group_name, no_randomize=False):
    '''policy prefix for user group'''
    # add rangom tag to avoid attempting to overwrite a previously created and deleted policy and silently failing.
    if no_randomize:
        tibanna_policy_prefix = 'tibanna_' + user_group_name
    else:
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
    if bucket_names:
        resource_list_buckets = ["arn:aws:s3:::" + bn for bn in bucket_names]
        resource_list_objects = ["arn:aws:s3:::" + bn + "/*" for bn in bucket_names]
    else:
        resource_list_buckets = "*"
        resource_list_objects = "*"
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
                    "s3:DeleteObject",
                    "s3:PutObjectAcl"
                ],
                "Resource": resource_list_objects
            }
        ]
    }
    return policy_bucket_access


def generate_policy_iam_passrole_s3(account_id, tibanna_policy_prefix):
    role_resource = ['arn:aws:iam::' + account_id + ':role/' + tibanna_policy_prefix + '_for_ec2']
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


def generate_cloudwatch_metric_policy(account_id, region, tibanna_policy_prefix):
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:PutMetricData",
                    "cloudwatch:GetMetricStatistics"
                ],
                "Resource": "*"
            }
        ]
    }
    return policy


def generate_cw_dashboard_policy(account_id, region, tibanna_policy_prefix):
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:PutDashboard"
                ],
                "Resource": "*"
            }
        ]
    }
    return policy


def generate_dynamodb_policy(account_id, region, tibanna_policy_prefix):
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:DescribeTable",
                    "dynamodb:PutItem"
                ],
                "Resource": "arn:aws:dynamodb:" + region + ":" + account_id + ":table/tibanna-master"
            }
        ]
    }
    return policy


def generate_ec2_desc_policy(account_id, region, tibanna_policy_prefix):
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:DescribeInstances",
                    "ec2:DescribeInstanceStatus"
                ],
                "Resource": "*"
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


def get_ec2_role_name(tibanna_policy_prefix):
    return tibanna_policy_prefix + '_for_ec2'


def get_lambda_role_name(tibanna_policy_prefix, lambda_name):
    return tibanna_policy_prefix + '_' + lambda_name


def get_stepfunction_role_name(tibanna_policy_prefix):
    return tibanna_policy_prefix + '_states'


def create_role_robust(client, rolename, roledoc, verbose=False):
    try:
        response = client.create_role(
           RoleName=rolename,
           AssumeRolePolicyDocument=roledoc
        )
    except Exception as e:
        if 'EntityAlreadyExists' in str(e):
            try:
                # first remove instance profiles attached to it
                res = client.list_instance_profiles_for_role(RoleName=rolename)
                for inst in res['InstanceProfiles']:
                    client.remove_role_from_instance_profile(
                        RoleName=rolename,
                        InstanceProfileName=inst['InstanceProfileName']
                    )
                # detach all policies
                iam = boto3.resource('iam')
                role = iam.Role(rolename)
                for pol in list(role.attached_policies.all()):
                    client.detach_role_policy(
                        RoleName=rolename,
                        PolicyArn=pol.arn
                    )
                # delete role
                client.delete_role(RoleName=rolename)
                # recreate
                response = client.create_role(
                   RoleName=rolename,
                   AssumeRolePolicyDocument=roledoc
                )
            except Exception as e2:
                raise Exception("Can't create role %s: %s" % (rolename, str(e2)))
    if verbose:
        print(response)


def create_empty_role_for_lambda(iam, verbose=False):
    client = iam.meta.client
    role_policy_doc_lambda = generate_assume_role_policy_document('lambda')
    empty_role_name = 'tibanna_lambda_init_role'
    try:
        client.get_role(RoleName=empty_role_name)
    except Exception:
        print("creating %s", empty_role_name)
        create_role_robust(client, empty_role_name, json.dumps(role_policy_doc_lambda), verbose)


def create_role_for_ec2(iam, tibanna_policy_prefix, account_id,
                        bucket_policy_name, cloudwatch_metric_policy_name,
                        verbose=False):
    client = iam.meta.client
    ec2_role_name = get_ec2_role_name(tibanna_policy_prefix)
    role_policy_doc_ec2 = generate_assume_role_policy_document('ec2')
    create_role_robust(client, ec2_role_name, json.dumps(role_policy_doc_ec2), verbose)
    role_bucket = iam.Role(ec2_role_name)
    response = role_bucket.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + bucket_policy_name
    )
    response = role_bucket.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + cloudwatch_metric_policy_name
    )
    if verbose:
        print(response)


def create_role_for_run_task_awsem(iam, tibanna_policy_prefix, account_id,
                                   cloudwatch_policy_name, bucket_policy_name,
                                   list_policy_name, passrole_policy_name,
                                   desc_stepfunction_policy_name,
                                   cw_dashboard_policy_name,
                                   dynamodb_policy_name,
                                   verbose=False):
    client = iam.meta.client
    lambda_run_role_name = get_lambda_role_name(tibanna_policy_prefix, 'run_task_awsem')
    role_policy_doc_lambda = generate_assume_role_policy_document('lambda')
    create_role_robust(client, lambda_run_role_name, json.dumps(role_policy_doc_lambda), verbose)
    role_lambda_run = iam.Role(lambda_run_role_name)
    for pn in [list_policy_name, cloudwatch_policy_name, passrole_policy_name,
               bucket_policy_name, dynamodb_policy_name, desc_stepfunction_policy_name,
               cw_dashboard_policy_name]:
        response = role_lambda_run.attach_policy(
            PolicyArn='arn:aws:iam::' + account_id + ':policy/' + pn
        )
        if verbose:
            print(response)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::aws:policy/AmazonEC2FullAccess'
    )
    if verbose:
        print(response)


def create_role_for_check_task_awsem(iam, tibanna_policy_prefix, account_id,
                                     cloudwatch_policy_name, bucket_policy_name,
                                     cloudwatch_metric_policy_name,
                                     verbose=False):
    client = iam.meta.client
    lambda_check_role_name = get_lambda_role_name(tibanna_policy_prefix, 'check_task_awsem')
    role_policy_doc_lambda = generate_assume_role_policy_document('lambda')
    create_role_robust(client, lambda_check_role_name, json.dumps(role_policy_doc_lambda), verbose)
    role_lambda_run = iam.Role(lambda_check_role_name)
    response = role_lambda_run.attach_policy(
        PolicyArn='arn:aws:iam::' + account_id + ':policy/' + cloudwatch_metric_policy_name
    )
    if verbose:
        print(response)
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
    create_role_robust(client, stepfunction_role_name, json.dumps(role_policy_doc), verbose)
    role_stepfunction = iam.Role(stepfunction_role_name)
    response = role_stepfunction.attach_policy(
        PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaRole'
        # PolicyArn='arn:aws:iam::' + account_id + ':policy/' + lambdainvoke_policy_name
    )
    if verbose:
        print(response)


def create_user_group(iam, group_name, bucket_policy_name, ec2_desc_policy_name,
                      dynamodb_policy_name,
                      account_id, verbose=False):
    client = iam.meta.client
    try:
        response = client.create_group(
           GroupName=group_name
        )
        if verbose:
            print(response)
    except Exception as e:
        if 'EntityAlreadyExists' in str(e):
            try:
                # do not actually delete the group, just detach existing policies.
                # deleting a group would require users to be detached from the group.
                for pol in list(iam.Group(group_name).attached_policies.all()):
                    res = client.detach_group_policy(GroupName=group_name, PolicyArn=pol.arn)
                    if verbose:
                        print(res)
            except Exception as e2:
                raise Exception("Can't detach policies from group %s : %s" % (group_name, str(e2)))
    group = iam.Group(group_name)
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
    response = group.attach_policy(
        PolicyArn='arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess'
    )
    if verbose:
        print(response)
    for pn in [bucket_policy_name, ec2_desc_policy_name, dynamodb_policy_name]:
        response = group.attach_policy(
            PolicyArn='arn:aws:iam::' + account_id + ':policy/' + pn
        )
        if verbose:
            print(response)


def create_policy_robust(client, policy_name, policy_doc, account_id, verbose=False):
    try:
        response = client.create_policy(
            PolicyName=policy_name,
            PolicyDocument=policy_doc,
        )
        if verbose:
            print(response)
    except Exception as e:
        if 'EntityAlreadyExists' in str(e):
            try:
                policy_arn = 'arn:aws:iam::' + account_id + ':policy/' + policy_name
                # first detach roles and groups and delete versions (requirements for deleting policy)
                res = client.list_entities_for_policy(PolicyArn=policy_arn)
                iam = boto3.resource('iam')
                policy = iam.Policy(policy_arn)
                for role in res['PolicyRoles']:
                    policy.detach_role(RoleName=role['RoleName'])
                for group in res['PolicyGroups']:
                    policy.detach_group(GroupName=group['GroupName'])
                for v in list(policy.versions.all()):
                    if not v.is_default_version:
                        client.delete_policy_version(PolicyArn=policy_arn, VersionId=v.version_id)
                # delete policy
                client.delete_policy(PolicyArn=policy_arn)
                # recreate policy
                response = client.create_policy(
                    PolicyName=policy_name,
                    PolicyDocument=policy_doc,
                )
                if verbose:
                    print(response)
            except Exception as e2:
                raise Exception("Can't create policy %s : %s" % (policy_name, str(e2)))


def create_tibanna_iam(account_id, bucket_names, user_group_name, region, verbose=False, no_randomize=False):
    """creates IAM policies and roles and a user group for tibanna
    returns prefix of all IAM policies, roles and group.
    Total 4 policies, 3 roles and 1 group is generated that is associated with a single user group
    A user group shares permission for buckets, tibanna execution and logs
    """
    # create prefix that represent a single user group
    tibanna_policy_prefix = generate_policy_prefix(user_group_name, no_randomize)
    iam = boto3.resource('iam')
    client = iam.meta.client
    # bucket policy
    bucket_policy_name = tibanna_policy_prefix + '_bucket_access'
    policy_ba = generate_policy_bucket_access(bucket_names)
    create_policy_robust(client, bucket_policy_name, json.dumps(policy_ba), account_id, verbose)
    # lambda policies
    # list_instanceprofiles : by default not user-dependent,
    # but create per user group to allow future modification per user-group
    list_policy_name = tibanna_policy_prefix + '_list_instanceprofiles'
    create_policy_robust(client, list_policy_name,
                         json.dumps(generate_policy_list_instanceprofiles()), account_id, verbose)
    # cloudwatchlogs: by default not user-dependent,
    # but create per user group to allow future modification per user-group
    cloudwatch_policy_name = tibanna_policy_prefix + '_cloudwatchlogs'
    create_policy_robust(client, cloudwatch_policy_name,
                         json.dumps(generate_policy_cloudwatchlogs()), account_id, verbose)
    # iam_passrole_s3: passrole policy per user group
    passrole_policy_name = tibanna_policy_prefix + '_iam_passrole_s3'
    policy_iam_ps3 = generate_policy_iam_passrole_s3(account_id, tibanna_policy_prefix)
    create_policy_robust(client, passrole_policy_name, json.dumps(policy_iam_ps3), account_id, verbose)
    # lambdainvoke policy for step function
    lambdainvoke_policy_name = tibanna_policy_prefix + '_lambdainvoke'
    policy_lambdainvoke = generate_lambdainvoke_policy(account_id, region, tibanna_policy_prefix)
    create_policy_robust(client, lambdainvoke_policy_name, json.dumps(policy_lambdainvoke), account_id, verbose)
    desc_stepfunction_policy_name = tibanna_policy_prefix + '_desc_sts'
    policy_desc_stepfunction = generate_desc_stepfunction_policy(account_id, region, tibanna_policy_prefix)
    create_policy_robust(client, desc_stepfunction_policy_name,
                         json.dumps(policy_desc_stepfunction), account_id, verbose)
    # permission to send cloudwatch metric (ec2)
    cloudwatch_metric_policy_name = tibanna_policy_prefix + '_cw_metric'
    policy_cloudwatch_metric = generate_cloudwatch_metric_policy(account_id, region, tibanna_policy_prefix)
    create_policy_robust(client, cloudwatch_metric_policy_name,
                         json.dumps(policy_cloudwatch_metric), account_id, verbose)
    # permission for cloudwatch dashboard creation (run_task_awsem)
    cw_dashboard_policy_name = tibanna_policy_prefix + '_cw_dashboard'
    policy_cw_dashboard = generate_cw_dashboard_policy(account_id, region, tibanna_policy_prefix)
    create_policy_robust(client, cw_dashboard_policy_name, json.dumps(policy_cw_dashboard), account_id, verbose)
    # permission for adding entries to dynamodb - user
    dynamodb_policy_name = tibanna_policy_prefix + '_dynamodb'
    policy_dynamodb = generate_dynamodb_policy(account_id, region, tibanna_policy_prefix)
    create_policy_robust(client, dynamodb_policy_name, json.dumps(policy_dynamodb), account_id, verbose)
    # ec2 describe policy for invoke stat -v (user)
    ec2_desc_policy_name = tibanna_policy_prefix + '_ec2_desc'
    policy_ec2_desc = generate_ec2_desc_policy(account_id, region, tibanna_policy_prefix)
    create_policy_robust(client, ec2_desc_policy_name, json.dumps(policy_ec2_desc), account_id, verbose)
    # roles
    # role for bucket
    create_role_for_ec2(iam, tibanna_policy_prefix, account_id,
                        bucket_policy_name, cloudwatch_metric_policy_name)
    # role for lambda
    create_role_for_run_task_awsem(iam, tibanna_policy_prefix, account_id,
                                   cloudwatch_policy_name, bucket_policy_name,
                                   list_policy_name, passrole_policy_name,
                                   desc_stepfunction_policy_name,
                                   cw_dashboard_policy_name, dynamodb_policy_name)
    create_role_for_check_task_awsem(iam, tibanna_policy_prefix, account_id,
                                     cloudwatch_policy_name, bucket_policy_name,
                                     cloudwatch_metric_policy_name)
    create_empty_role_for_lambda(iam)
    # role for step function
    create_role_for_stepfunction(iam, tibanna_policy_prefix, account_id, lambdainvoke_policy_name)
    # instance profile
    # create instance profile
    instance_profile_name = get_ec2_role_name(tibanna_policy_prefix)
    try:
        client.create_instance_profile(
            InstanceProfileName=instance_profile_name
        )
    except Exception as e:
        if 'EntityAlreadyExists' in str(e):
            client.delete_instance_profile(InstanceProfileName=instance_profile_name)
            try:
                client.create_instance_profile(
                    InstanceProfileName=instance_profile_name
                )
            except Exception as e2:
                raise Exception("Can't create instance profile %s: %s" % (instance_profile_name, str(e2)))
    # add role to instance profile
    ip = iam.InstanceProfile(instance_profile_name)
    try:
        ip.add_role(
            RoleName=instance_profile_name
        )
    except Exception as e:
        if 'LimitExceeded' in e:
            ip.remove_role(instance_profile_name)
            try:
                ip.add_role(
                    RoleName=instance_profile_name
                )
            except Exception as e2:
                raise Exception("Can't add role %s: %s" % (instance_profile_name, str(e2)))
    # create IAM group for users who share permission
    create_user_group(iam, tibanna_policy_prefix, bucket_policy_name, ec2_desc_policy_name,
                      dynamodb_policy_name, account_id)
    return tibanna_policy_prefix
