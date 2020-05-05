from .vars import AWS_REGION, AWS_ACCOUNT_NUMBER


class StepFunctionUnicorn(object):
    lambda_error_retry_condition = {
        "ErrorEquals": [ "Lambda.ServiceException",
                         "Lambda.AWSLambdaException",
                         "Lambda.SdkClientException",
                         "Lambda.ResourceNotFoundException"],
        "IntervalSeconds": 60,
        "MaxAttempts": 6,
        "BackoffRate": 2
    }

    sfn_run_task_retry_conditions = [
        {
            "ErrorEquals": ["DependencyStillRunningException"],
            "IntervalSeconds": 600,
            "MaxAttempts": 10000,
            "BackoffRate": 1.0
        },
        {
            "ErrorEquals": ["EC2InstanceLimitWaitException"],
            "IntervalSeconds": 600,
            "MaxAttempts": 1008,  # 1 wk
            "BackoffRate": 1.0
        },
        lambda_error_retry_condition
    ]

    sfn_check_task_retry_conditions = [
        {
            "ErrorEquals": ["EC2StartingException"],
            "IntervalSeconds": 300,
            "MaxAttempts": 25,
            "BackoffRate": 1.0
        },
        {
            "ErrorEquals": ["StillRunningException"],
            "IntervalSeconds": 300,
            "MaxAttempts": 100000,
            "BackoffRate": 1.0
        },
        lambda_error_retry_condition
    ]

    def __init__(self,
                 dev_suffix=None,
                 region_name=AWS_REGION,
                 aws_acc=AWS_ACCOUNT_NUMBER,
                 usergroup=None):
        self.dev_suffix = dev_suffix
        self.region_name = region_name
        self.aws_acc = aws_acc
        self.usergroup = usergroup

    @property
    def lambda_suffix(self):
        if self.usergroup:
            if self.dev_suffix:
                lambda_suffix = '_' + self.usergroup + '_' + self.dev_suffix
            else:
                lambda_suffix = '_' + self.usergroup
        else:
            if self.dev_suffix:
                lambda_suffix = '_' + self.dev_suffix
            else:
                lambda_suffix = ''
        return lambda_suffix

    @property
    def lambda_arn_prefix(self):
        return "arn:aws:lambda:" + self.region_name + ":" + self.aws_acc + ":function:"

    @property
    def sfn_name(self):
        return 'tibanna_unicorn' + self.lambda_suffix

    @property
    def iam(self):
        from .iam_utils import IAM
        return IAM(self.usergroup)

    @property
    def sfn_role_arn(self):
        if not self.usergroup:  # 4dn
            sfn_role_arn = "arn:aws:iam::" + self.aws_acc + \
                           ":role/service-role/StatesExecutionRole-" + self.region_name
        else:
            sfn_role_arn = "arn:aws:iam::" + self.aws_acc + ":role/" + \
                           self.iam.role_name('stepfunction')
        return sfn_role_arn

    @property
    def sfn_start_lambda(self):
        return 'RunTaskAwsem'

    @property
    def sfn_state_defs(self):
        state_defs = {
            "RunTaskAwsem": {
                "Type": "Task",
                "Resource": self.lambda_arn_prefix + "run_task_awsem" + self.lambda_suffix,
                "Retry": self.sfn_run_task_retry_conditions,
                "Next": "CheckTaskAwsem"
            },
            "CheckTaskAwsem": {
                "Type": "Task",
                "Resource": self.lambda_arn_prefix + "check_task_awsem" + self.lambda_suffix,
                "Retry": self.sfn_check_task_retry_conditions,
                "End": True
            }
        }
        return state_defs

    @property
    def description(self):
        return "Start a workflow run on awsem and track it"

    @property
    def definition(self):
        return {
          "Comment": self.description,
          "StartAt": self.sfn_start_lambda,
          "States": self.sfn_state_defs
        }
