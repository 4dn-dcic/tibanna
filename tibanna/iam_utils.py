import boto3
import json
import random
from .vars import DYNAMODB_TABLE, AWS_ACCOUNT_NUMBER, AWS_REGION
from .utils import printlog


class IAM(object):

    account_id = AWS_ACCOUNT_NUMBER
    region = AWS_REGION
    lambda_type = ''  # lambda_type : '' for unicorn, 'pony' for pony, 'zebra' for zebra
    run_task_lambda_name='run_task_awsem'
    check_task_lambda_name='check_task_awsem'

    def __init__(self, bucket_names, user_group_name):
        self.bucket_names = bucket_names
        self.user_group_name = user_group_name
        self.lambda_names = [self.run_task_lambda_name, self.check_task_lambda_name]
        self.client = boto3.client('iam')
        self.iam = boto3.resource('iam')

    @property
    def iam_group_name(self):
        return self.tibanna_policy_prefix
 
    def generate_policy_prefix(self, no_randomize=False):
        """policy prefix for user group
        lambda_type : '' for unicorn, 'pony' for pony, 'zebra' for zebra"""
        # add rangom tag to avoid attempting to overwrite a previously created and deleted policy and silently failing.
        if self.lambda_type:
            prefix = 'tibanna_' + self.lambda_type + '_'
        else:
            prefix = 'tibanna_'
        if no_randomize:
            self.tibanna_policy_prefix = prefix + self.user_group_name
        else:
            random_tag = str(int(random.random() * 10000))
            self.tibanna_policy_prefix = prefix + self.user_group_name + '_' + random_tag

    def policy_suffix(self, policy_type):
        suffices = {'bucket': 'bucket_access',
                    'termination': 'ec2_termination',
                    'list': 'list_instanceprofiles',
                    'cloudwatch': 'cloudwatchlogs',
                    'passrole': 'iam_passrole_s3',
                    'lambdainvoke': 'lambdainvoke',
                    'desc_stepfunction': 'desc_sts',
                    'cloudwatch_metric': 'cw_metric',
                    'cw_dashboard': 'cw_dashboard',
                    'dynamodb': 'dynamodb',
                    'ec2_desc': 'ec2_desc'}
        if policy_type not in suffices:
            raise Exception("policy %s must be one of %s." % (policy_type, str(suffices)))
        return suffices[policy_type]

    def policy_name(self, policy_type):
        return self.tibanna_policy_prefix + '_' + self.policy_suffix(policy_type)

    def policy_definition(self, policy_type):
        definitions = {'bucket': self.policy_bucket_access,
                       'termination': self.policy_terminate_instances,
                       'list': self.policy_list_instanceprofiles,
                       'cloudwatch': self.policy_cloudwatchlogs,
                       'passrole': self.policy_iam_passrole_s3,
                       'lambdainvoke': self.policy_lambdainvoke,
                       'desc_stepfunction': self.policy_desc_stepfunction,
                       'cloudwatch_metric': self.policy_cloudwatch_metric,
                       'cw_dashboard': self.policy_cw_dashboard,
                       'dynamodb': self.policy_dynamodb,
                       'ec2_desc': self.policy_ec2_desc_policy}
        if policy_type not in definitions:
            raise Exception("policy %s must be one of %s." % (policy_type, str(definitions)))
        return definitions[policy_type]

    @property
    def policy_bucket_access(self):
        if self.bucket_names:
            resource_list_buckets = ["arn:aws:s3:::" + bn for bn in self.bucket_names]
            resource_list_objects = ["arn:aws:s3:::" + bn + "/*" for bn in self.bucket_names]
        else:
            resource_list_buckets = ["arn:aws:s3:::" + "my-tibanna-test-bucket",
                                     "arn:aws:s3:::" + "my-tibanna-test-input-bucket"]
            resource_list_objects = ["arn:aws:s3:::" + "my-tibanna-test-bucket/*",
                                     "arn:aws:s3:::" + "my-tibanna-test-input-bucket/*"]
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
    
    @property
    def policy_terminate_instances(self):
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "ec2:TerminateInstances",
                    "Resource": "*"
                }
            ]
        }
        return policy
    
    @property
    def policy_list_instanceprofiles(self):
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
    
    @property
    def policy_cloudwatchlogs(self):
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
    
    @property
    def policy_iam_passrole_s3(self):
        role_resource = ['arn:aws:iam::' + self.account_id + ':role/' + self.tibanna_policy_prefix + '_for_ec2']
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
    
    @property
    def policy_lambdainvoke(self):
        function_arn_prefix = 'arn:aws:lambda:' + self.region + ':' + self.account_id + ':function/'
        resource = [function_arn_prefix + ln + '_' + self.tibanna_policy_prefix for ln in self.lambda_names]
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
    
    @property
    def policy_desc_stepfunction(self):
        execution_arn_prefix = 'arn:aws:states:' + self.region + ':' + self.account_id + ':execution:'
        resource = execution_arn_prefix + '*' + self.user_group_name + ':*'
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
    
    @property
    def policy_cloudwatch_metric(self):
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
   
    @property
    def policy_cw_dashboard(self):
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
    
    @property
    def policy_dynamodb(self):
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:DescribeTable",
                        "dynamodb:PutItem"
                    ],
                    "Resource": "arn:aws:dynamodb:" + self.region + ":" + self.account_id + ":table/" + DYNAMODB_TABLE
                }
            ]
        }
        return policy
    
    @property
    def policy_ec2_desc_policy(self):
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
   
    def generate_assume_role_policy_document(self, service):
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
    
    def ec2_role_name(self):
        return self.tibanna_policy_prefix + '_for_ec2'
    
    def lambda_role_name(self, lambda_name):
        return self.tibanna_policy_prefix + '_' + lambda_name
    
    def stepfunction_role_name(self):
        return self.tibanna_policy_prefix + '_states'

    def remove_role(self, rolename):
        # first remove instance profiles attached to it
        res = self.client.list_instance_profiles_for_role(RoleName=rolename)
        for inst in res['InstanceProfiles']:
            self.client.remove_role_from_instance_profile(
                RoleName=rolename,
                InstanceProfileName=inst['InstanceProfileName']
            )
        # detach all policies
        role = self.iam.Role(rolename)
        for pol in list(role.attached_policies.all()):
            self.client.detach_role_policy(
                RoleName=rolename,
                PolicyArn=pol.arn
            )
        # delete role
        self.client.delete_role(RoleName=rolename)
    
    def create_role_robust(self, rolename, roledoc, verbose=False):
        try:
            response = self.client.create_role(
               RoleName=rolename,
               AssumeRolePolicyDocument=roledoc
            )
        except Exception as e:
            if 'EntityAlreadyExists' in str(e):
                try:
                    # first remove
                    self.remove_role(rolename)
                    # recreate
                    response = self.client.create_role(
                       RoleName=rolename,
                       AssumeRolePolicyDocument=roledoc
                    )
                except Exception as e2:
                    raise Exception("Can't create role %s: %s" % (rolename, str(e2)))
        if verbose:
            print(response)
    
    def create_empty_role_for_lambda(self, verbose=False):
        role_policy_doc_lambda = self.generate_assume_role_policy_document('lambda')
        empty_role_name = 'tibanna_lambda_init_role'
        try:
            self.client.get_role(RoleName=empty_role_name)
        except Exception:
            print("creating %s", empty_role_name)
            self.create_role_robust(empty_role_name, json.dumps(role_policy_doc_lambda), verbose)
    
    def create_role_for_ec2(self, verbose=False):
        role_policy_doc_ec2 = self.generate_assume_role_policy_document('ec2')
        self.create_role_robust(self.ec2_role_name, json.dumps(role_policy_doc_ec2), verbose)
        role_bucket = self.iam.Role(self.ec2_role_name())
        response = role_bucket.attach_policy(
            PolicyArn='arn:aws:iam::' + self.account_id + ':policy/' + self.policy_name('bucket')
        )
        response = role_bucket.attach_policy(
            PolicyArn='arn:aws:iam::' + self.account_id + ':policy/' + self.policy_name('cloudwatch_metric')
        )
        if verbose:
            print(response)
    
    def create_role_for_run_task_awsem(self, verbose=False):
        lambda_run_role_name = self.lambda_role_name(self.run_task_lambda_name)
        role_policy_doc_lambda = self.generate_assume_role_policy_document('lambda')
        self.create_role_robust(lambda_run_role_name, json.dumps(role_policy_doc_lambda), verbose)
        role_lambda_run = self.iam.Role(lambda_run_role_name)
        custom_policy_types = ['list', 'cloudwatch', 'passrole', 'bucket', 'dynamodb', 'desc_stepfunction', 'cw_dashboard']
        for pn in [self.policy_name(pt) for pt in custom_policy_types]
            response = role_lambda_run.attach_policy(
                PolicyArn='arn:aws:iam::' + self.account_id + ':policy/' + pn
            )
            if verbose:
                print(response)
        response = role_lambda_run.attach_policy(
            PolicyArn='arn:aws:iam::aws:policy/AmazonEC2FullAccess'
        )
        if verbose:
            print(response)
    
    def create_role_for_check_task_awsem(self, verbose=False):
        lambda_check_role_name = self.lambda_role_name(self.check_task_lambda_name)
        role_policy_doc_lambda = self.generate_assume_role_policy_document('lambda')
        self.create_role_robust(lambda_check_role_name, json.dumps(role_policy_doc_lambda), verbose)
        role_lambda_run = self.iam.Role(lambda_check_role_name)
        custom_policy_types = ['cloudwatch_metric', 'cloudwatch', 'bucket', 'ec2_desc', 'termination']
        for pn in [self.policy_name(pt) for pt in custom_policy_types]
            response = role_lambda_run.attach_policy(
                PolicyArn='arn:aws:iam::' + self.account_id + ':policy/' + pn
            )
            if verbose:
                print(response)
    
    def create_role_for_stepfunction(self, verbose=False):
        role_policy_doc = self.generate_assume_role_policy_document('states')
        self.create_role_robust(self.stepfunction_role_name(), json.dumps(role_policy_doc), verbose)
        role_stepfunction = self.iam.Role(self.stepfunction_role_name())
        response = role_stepfunction.attach_policy(
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaRole'
            # PolicyArn='arn:aws:iam::' + account_id + ':policy/' + lambdainvoke_policy_name
        )
        if verbose:
            print(response)
    
    def detach_policies_from_group(self):
        try:
            # do not actually delete the group, just detach existing policies.
            # deleting a group would require users to be detached from the group.
            for pol in list(self.iam.Group(self.iam_group_name).attached_policies.all()):
                res = self.client.detach_group_policy(GroupName=self.iam_group_name, PolicyArn=pol.arn)
                if verbose:
                    print(res)
        except Exception as e2:
            raise Exception("Can't detach policies from group %s : %s" % (self.iam_group_name, str(e2)))
    
    def create_user_group(self, verbose=False):
        try:
            response = self.client.create_group(
               GroupName=self.iam_group_name
            )
            if verbose:
                print(response)
        except Exception as e:
            if 'EntityAlreadyExists' in str(e):
                # do not actually delete the group, just detach existing policies.
                # deleting a group would require users to be detached from the group.
                self.detach_policies_from_group()
        group = self.iam.Group(self.iam_group_name)
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
        custom_policy_types = ['bucket', 'ec2_desc', 'cloudwatch_metric', 'dynamodb', 'termination']
        for pn in [self.policy_name(pt) for pt in custom_policy_types]
            response = group.attach_policy(
                PolicyArn='arn:aws:iam::' + self.account_id + ':policy/' + pn
            )
            if verbose:
                print(response)
    
    def remove_policy(client, policy_name, account_id):
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
                    # first delete policy
                    remove_policy(client, policy_name, account_id)
                    # recreate policy
                    response = client.create_policy(
                        PolicyName=policy_name,
                        PolicyDocument=policy_doc,
                    )
                    if verbose:
                        print(response)
                except Exception as e2:
                    raise Exception("Can't create policy %s : %s" % (policy_name, str(e2)))
    
    def remove_instance_profile(client, instance_profile_name):
        try:
            client.delete_instance_profile(InstanceProfileName=instance_profile_name)
        except Exception as e:
            raise Exception("Can't delete instance profile. %s" % str(e))
    
    def create_tibanna_iam(account_id, bucket_names, user_group_name, region, verbose=False, no_randomize=False,
                           run_task_lambda_name='run_task_awsem', check_task_lambda_name='check_task_awsem',
                           lambda_type=''):
        """creates IAM policies and roles and a user group for tibanna
        returns prefix of all IAM policies, roles and group.
        Total 4 policies, 3 roles and 1 group is generated that is associated with a single user group
        A user group shares permission for buckets, tibanna execution and logs
        """
        # create prefix that represent a single user group
        tibanna_policy_prefix = generate_policy_prefix(user_group_name, no_randomize, lambda_type=lambda_type)
        printlog("creating iam permissions with tibanna policy prefix %s" % tibanna_policy_prefix)
        iam = boto3.resource('iam')
        client = iam.meta.client
        # bucket policy
        bucket_policy_name = tibanna_policy_prefix + '_bucket_access'
        policy_ba = generate_policy_bucket_access(bucket_names)
        create_policy_robust(client, bucket_policy_name, json.dumps(policy_ba), account_id, verbose)
        # EC2 termination policy
        termination_policy_name = tibanna_policy_prefix + '_ec2_termination'
        create_policy_robust(client, termination_policy_name,
                             json.dumps(generate_policy_terminate_instances()), account_id, verbose)
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
        policy_lambdainvoke = generate_lambdainvoke_policy(account_id, region, tibanna_policy_prefix,
                                                           lambda_names=lambda_names)
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
                                       cw_dashboard_policy_name, dynamodb_policy_name,
                                       run_task_lambda_name=run_task_lambda_name)
        create_role_for_check_task_awsem(iam, tibanna_policy_prefix, account_id,
                                         cloudwatch_policy_name, bucket_policy_name,
                                         cloudwatch_metric_policy_name,
                                         ec2_desc_policy_name, termination_policy_name,
                                         check_task_lambda_name=check_task_lambda_name)
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
                remove_instance_profile(client,nstanceProfileName=instance_profile_name)
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
        self.create_user_group()
        return tibanna_policy_prefix
