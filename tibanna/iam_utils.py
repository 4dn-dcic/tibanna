import boto3
import json
import random
from . import create_logger
from .vars import (
    DYNAMODB_TABLE,
    AWS_ACCOUNT_NUMBER,
    AWS_REGION,
    LAMBDA_TYPE,
    RUN_TASK_LAMBDA_NAME,
    CHECK_TASK_LAMBDA_NAME
)


logger = create_logger(__name__)


class IAM(object):

    account_id = AWS_ACCOUNT_NUMBER
    region = AWS_REGION
    lambda_type = LAMBDA_TYPE  # lambda_type : '' for unicorn, 'pony' for pony, 'zebra' for zebra
    run_task_lambda_name = RUN_TASK_LAMBDA_NAME
    check_task_lambda_name = CHECK_TASK_LAMBDA_NAME

    def __init__(self, user_group_tag, bucket_names='', no_randomize=True):
        """policy prefix for user group
        lambda_type : '' for unicorn, 'pony' for pony, 'zebra' for zebra
        example>
          user_group_tag : default
          user_group_name : default_3465
          tibanna_policy_prefix : tibanna_default_3465 / tibanna_pony_default_3465
          prefix : tibanna_ / tibanna_pony_
        """
        # lambda names
        self.lambda_names = [self.run_task_lambda_name, self.check_task_lambda_name]
        if self.lambda_type:
            self.prefix = 'tibanna_' + self.lambda_type + '_'
        else:
            self.prefix = 'tibanna_'

        # user group name & tibanna_policy_prefix
        self.user_group_tag = user_group_tag
        # add rangom tag to avoid attempting to overwrite a previously created and deleted policy and silently failing.
        if no_randomize:
            self.user_group_name = self.user_group_tag
        else:
            random_tag = str(int(random.random() * 10000))
            self.user_group_name = self.user_group_tag + '_' + random_tag
        self.tibanna_policy_prefix = self.prefix + self.user_group_name

        # bucket names
        self.bucket_names = bucket_names

        # iam client/resource
        self.client = boto3.client('iam')
        self.iam = boto3.resource('iam')

    @property
    def iam_group_name(self):
        return self.tibanna_policy_prefix

    @property
    def policy_types(self):
        return ['bucket', 'termination', 'list', 'cloudwatch', 'passrole', 'lambdainvoke',
                'desc_stepfunction', 'cloudwatch_metric', 'cw_dashboard', 'dynamodb', 'ec2_desc']

    def policy_arn(self, policy_type):
        return 'arn:aws:iam::' + self.account_id + ':policy/' + self.policy_name(policy_type)

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
            raise Exception("policy %s must be one of %s." % (policy_type, str(self.policy_types)))
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
            raise Exception("policy %s must be one of %s." % (policy_type, str(self.policy_types)))
        return definitions[policy_type]

    @property
    def role_types(self):
        return ['ec2', 'stepfunction'] + self.lambda_names

    def role_suffix(self, role_type):
        suffices = {'ec2': 'for_ec2',
                    'stepfunction': 'states'}
        suffices.update({_: _ for _ in self.lambda_names})
        if role_type not in suffices:
            raise Exception("role_type %s must be one of %s." % (role_type, str(self.role_types)))
        return suffices[role_type]

    def role_name(self, role_type):
        return self.tibanna_policy_prefix + '_' + self.role_suffix(role_type)

    def role_service(self, role_type):
        services = {'ec2': 'ec2',
                    'stepfunction': 'states'}
        services.update({_: 'lambda' for _ in self.lambda_names})
        if role_type not in services:
            raise Exception("role_type %s must be one of %s." % (role_type, str(self.role_types)))
        return services[role_type]

    def policy_arn_list_for_role(self, role_type):
        run_task_custom_policy_types = ['list', 'cloudwatch', 'passrole', 'bucket', 'dynamodb',
                                        'desc_stepfunction', 'cw_dashboard']
        check_task_custom_policy_types = ['cloudwatch_metric', 'cloudwatch', 'bucket', 'ec2_desc',
                                          'termination']
        arnlist = {'ec2': [self.policy_arn(_) for _ in ['bucket', 'cloudwatch_metric']] +
                          ['arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly'],
                   # 'stepfunction': [self.policy_arn(_) for _ in ['lambdainvoke']],
                   'stepfunction': ['arn:aws:iam::aws:policy/service-role/AWSLambdaRole'],
                   self.run_task_lambda_name: [self.policy_arn(_) for _ in run_task_custom_policy_types] +
                                              ['arn:aws:iam::aws:policy/AmazonEC2FullAccess'],
                   self.check_task_lambda_name: [self.policy_arn(_) for _ in check_task_custom_policy_types]}
        if role_type not in arnlist:
            raise Exception("role_type %s must be one of %s." % (role_type, str(self.role_types)))
        return arnlist[role_type]

    @property
    def instance_profile_name(self):
        return self.role_name('ec2')

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
        resource = execution_arn_prefix + self.tibanna_policy_prefix + ':*'
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

    def role_policy_document(self, service):
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
                    self.remove_role(rolename, ignore_errors=False)
                    # recreate
                    response = self.client.create_role(
                       RoleName=rolename,
                       AssumeRolePolicyDocument=roledoc
                    )
                except Exception as e2:
                    raise Exception("Can't create role %s: %s" % (rolename, str(e2)))
        if verbose:
            logger.debug("response from create_role_robust: " + str(response))

    def create_empty_role_for_lambda(self, verbose=False):
        role_policy_doc_lambda = self.role_policy_document('lambda')
        empty_role_name = 'tibanna_lambda_init_role'
        try:
            self.client.get_role(RoleName=empty_role_name)
        except Exception:
            logger.info("creating %s", empty_role_name)
            self.create_role_robust(empty_role_name, json.dumps(role_policy_doc_lambda), verbose)

    def create_role_for_role_type(self, role_type, verbose=False):
        role_policy_doc = self.role_policy_document(self.role_service(role_type))
        self.create_role_robust(self.role_name(role_type), json.dumps(role_policy_doc), verbose)
        role = self.iam.Role(self.role_name(role_type))
        for p_arn in self.policy_arn_list_for_role(role_type):
            response = role.attach_policy(PolicyArn=p_arn)
            if verbose:
                logger.debug("response from IAM attach_policy :" + str(response))

    def create_user_group(self, verbose=False):
        try:
            response = self.client.create_group(
               GroupName=self.iam_group_name
            )
            if verbose:
                logger.debug("response from IAM create_group :" + str(response))
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
            logger.debug("response from IAM attach_policy :" + str(response))
        response = group.attach_policy(
            PolicyArn='arn:aws:iam::aws:policy/AWSStepFunctionsConsoleFullAccess'
        )
        if verbose:
            logger.debug("response from IAM attach_policy :" + str(response))
        response = group.attach_policy(
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )
        if verbose:
            logger.debug("response from IAM attach_policy :" + str(response))
        response = group.attach_policy(
            PolicyArn='arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess'
        )
        if verbose:
            logger.debug("response from IAM attach_policy :" + str(response))
        custom_policy_types = ['bucket', 'ec2_desc', 'cloudwatch_metric', 'dynamodb', 'termination']
        for pn in [self.policy_name(pt) for pt in custom_policy_types]:
            response = group.attach_policy(
                PolicyArn='arn:aws:iam::' + self.account_id + ':policy/' + pn
            )
            if verbose:
                logger.debug("response from IAM attach_policy :" + str(response))

    def create_policy_robust(self, policy_name, policy_doc, verbose=False):
        try:
            response = self.client.create_policy(
                PolicyName=policy_name,
                PolicyDocument=policy_doc,
            )
            if verbose:
                logger.debug("response from IAM create_policy :" + str(response))
        except Exception as e:
            if 'EntityAlreadyExists' in str(e):
                try:
                    # first delete policy
                    self.remove_policy(policy_name, ignore_errors=False)
                    # recreate policy
                    response = self.client.create_policy(
                        PolicyName=policy_name,
                        PolicyDocument=policy_doc,
                    )
                    if verbose:
                        logger.debug("response from IAM create_policy :" + str(response))
                except Exception as e2:
                    raise Exception("Can't create policy %s : %s" % (policy_name, str(e2)))

    def create_instance_profile(self, verbose=False):
        try:
            self.client.create_instance_profile(
                InstanceProfileName=self.instance_profile_name
            )
        except Exception as e:
            if 'EntityAlreadyExists' in str(e):
                self.remove_instance_profile(ignore_errors=False)
                try:
                    self.client.create_instance_profile(
                        InstanceProfileName=self.instance_profile_name
                    )
                except Exception as e2:
                    raise Exception("Can't create instance profile %s: %s" % (self.instance_profile_name, str(e2)))
        # add role to instance profile
        ip = self.iam.InstanceProfile(self.instance_profile_name)
        try:
            ip.add_role(
                RoleName=self.instance_profile_name
            )
        except Exception as e:
            if 'LimitExceeded' in e:
                ip.remove_role(self.instance_profile_name, ignore_errors=False)
                try:
                    ip.add_role(
                        RoleName=self.instance_profile_name
                    )
                except Exception as e2:
                    raise Exception("Can't add role %s: %s" % (self.instance_profile_name, str(e2)))

    def create_tibanna_iam(self, verbose=False):
        """creates IAM policies and roles and a user group for tibanna
        returns prefix of all IAM policies, roles and group.
        Total 4 policies, 3 roles and 1 group is generated that is associated with a single user group
        A user group shares permission for buckets, tibanna execution and logs
        """
        # create prefix that represent a single user group
        logger.info("creating iam permissions with tibanna policy prefix %s" % self.tibanna_policy_prefix)

        # policies
        for pt in self.policy_types:
            self.create_policy_robust(self.policy_name(pt), json.dumps(self.policy_definition(pt)), verbose)

        # roles
        for rt in self.role_types:
            self.create_role_for_role_type(rt, verbose)
        # initial empty role for lambda
        self.create_empty_role_for_lambda(verbose)

        # instance profile
        # create instance profile
        self.create_instance_profile(verbose)
        # create IAM group for users who share permission
        self.create_user_group()
        return self.tibanna_policy_prefix

    def remove_role(self, rolename, verbose=False, ignore_errors=True):
        if verbose:
            logger.info("removing role %s" % rolename)
        try:
            role = self.iam.Role(rolename)
            role.description
        except Exception as e:
            if 'ResourceNotFound' in str(e) or 'NoSuchEntity' in str(e):
                if ignore_errors:
                    if verbose:
                        logger.info("role %s doesn't exist. skipping." % rolename)
                    return
                else:
                    raise Exception(e)
            raise Exception("Can't delete role %s. %s" % (rolename, str(e)))
        # first remove instance profiles attached to it
        res = self.client.list_instance_profiles_for_role(RoleName=rolename)
        for inst in res['InstanceProfiles']:
            res2 = self.client.remove_role_from_instance_profile(
                RoleName=rolename,
                InstanceProfileName=inst['InstanceProfileName']
            )
        # detach all policies
        for pol in list(role.attached_policies.all()):
            res2 = self.client.detach_role_policy(
                RoleName=rolename,
                PolicyArn=pol.arn
            )
        # delete role
        res2 = self.client.delete_role(RoleName=rolename)

    def remove_roles(self, verbose=False, ignore_errors=True):
        for rn in [self.role_name(rt) for rt in self.role_types]:
            self.remove_role(rn, verbose=verbose, ignore_errors=ignore_errors)

    def remove_instance_profile(self, verbose=False, ignore_errors=True):
        if verbose:
            logger.info("removing instance profile %s" % self.instance_profile_name)
        try:
            res = self.client.delete_instance_profile(InstanceProfileName=self.instance_profile_name)
        except Exception as e:
            if 'ResourceNotFound' in str(e) or 'NoSuchEntity' in str(e):
                if ignore_errors:
                    if verbose:
                        logger.info("instance profile %s doesn't exist. skipping." % self.instance_profile_name)
                    return
                else:
                    raise Exception(e)
            raise Exception("Can't delete instance profile. %s" % str(e))

    def remove_policy(self, policy_name, verbose=False, ignore_errors=True):
        if verbose:
            logger.info("removing policy %s" % policy_name)
        policy_arn = 'arn:aws:iam::' + self.account_id + ':policy/' + policy_name
        # first detach roles and groups and delete versions (requirements for deleting policy)
        try:
            policy = self.iam.Policy(policy_arn)
            policy.description
        except Exception as e:
            if 'ResourceNotFound' in str(e) or 'NoSuchEntity' in str(e):
                if ignore_errors:
                    if verbose:
                        logger.info("policy %s doesn't exist. skipping." % policy_arn)
                    return
                else:
                    raise Exception(e)
            raise Exception("Can't delete policy %s. %s" % (policy_arn, str(e)))
        res = self.client.list_entities_for_policy(PolicyArn=policy_arn)
        for role in res['PolicyRoles']:
            res2 = policy.detach_role(RoleName=role['RoleName'])
        for group in res['PolicyGroups']:
            res2 = policy.detach_group(GroupName=group['GroupName'])
        for v in list(policy.versions.all()):
            if not v.is_default_version:
                res2 = self.client.delete_policy_version(PolicyArn=policy_arn, VersionId=v.version_id)
        # delete policy
        res2 = self.client.delete_policy(PolicyArn=policy_arn)

    def remove_policies(self, verbose=False, ignore_errors=True):
        for pn in [self.policy_name(pt) for pt in self.policy_types]:
            self.remove_policy(pn, verbose=verbose, ignore_errors=ignore_errors)

    def detach_policies_from_group(self, verbose=False):
        try:
            # do not actually delete the group, just detach existing policies.
            # deleting a group would require users to be detached from the group.
            for pol in list(self.iam.Group(self.iam_group_name).attached_policies.all()):
                res = self.client.detach_group_policy(GroupName=self.iam_group_name, PolicyArn=pol.arn)
        except Exception as e2:
            raise Exception("Can't detach policies from group %s : %s" % (self.iam_group_name, str(e2)))

    def remove_users_from_group(self, verbose=False):
        gr = self.iam.Group(self.iam_group_name)
        for u in gr.users.iterator():
            gr.remove_user(UserName=u.user_name)

    def delete_group(self, verbose=False, ignore_errors=True):
        if verbose:
            logger.info("removing group %s" % self.iam_group_name)
        try:
            gr = self.iam.Group(self.iam_group_name)
            gr.group_id
        except Exception as e:
            if 'ResourceNotFound' in str(e) or 'NoSuchEntity' in str(e):
                if ignore_errors:
                    if verbose:
                        logger.info("group %s doesn't exist. skipping." % self.iam_group_name)
                    return
                else:
                    raise Exception(e)
            raise Exception("Can't delete policy %s. %s" % (self.iam_group_name, str(e)))

        self.remove_users_from_group(verbose)
        self.detach_policies_from_group(verbose)
        gr.delete()

    def delete_tibanna_iam(self, verbose=True, ignore_errors=True):
        self.remove_policies(verbose=verbose, ignore_errors=ignore_errors)
        self.remove_roles(verbose=verbose, ignore_errors=ignore_errors)
        self.remove_instance_profile(verbose=verbose, ignore_errors=ignore_errors)
        res = self.delete_group(verbose=verbose, ignore_errors=ignore_errors)
