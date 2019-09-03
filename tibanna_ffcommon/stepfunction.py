from .vars import AWS_REGION, AWS_ACCOUNT_NUMBER
from tibanna.stepfunction import StepFunctionUnicorn


class StepFunctionFFAbstract(StepFunctionUnicorn):
    sfn_start_run_retry_conditions = [
        {
            "ErrorEquals": ["TibannaStartException"],
            "IntervalSeconds": 30,
            "MaxAttempts": 5,
            "BackoffRate": 1.0
        },
        {
            "ErrorEquals": ["FdnConnectionException"],
            "IntervalSeconds": 30,
            "MaxAttempts": 5,
            "BackoffRate": 1.0
        }
    ]
    sfn_update_ff_meta_retry_conditions = [
        {
            "ErrorEquals": ["TibannaStartException"],
            "IntervalSeconds": 30,
            "MaxAttempts": 5,
            "BackoffRate": 1.0
        }
    ]

    def __init__(self,
                 dev_suffix=None,
                 region_name=AWS_REGION,
                 aws_acc=AWS_ACCOUNT_NUMBER,
                 usergroup=None):
        super().__init__(dev_suffix, region_name, aws_acc, usergroup)

    @property
    def sfn_name(self):
        return 'tibanna_' + self.lambda_type + self.lambda_suffix

    @property
    def sfn_role_arn(self):
        return "arn:aws:iam::" + self.aws_acc + \
               ":role/service-role/StatesExecutionRole-" + self.region_name

    @property
    def sfn_start_lambda(self):
        return 'StartRunAwsem'

    @property
    def lambda_type(self):
        """This should be 'pony' or 'zebra' for the real class.
        'ffcommon' is not actually used. Just a placeholder."""
        return 'ffcommon'

    @property
    def sfn_state_defs(self):
        state_defs = {
            "StartRunAwsem": {
                "Type": "Task",
                "Resource": self.lambda_arn_prefix + "start_run_" + self.lambda_type + self.lambda_suffix,
                "Retry": self.sfn_start_run_retry_conditions,
                "Next": "RunTaskAwsem"
            },
            "RunTaskAwsem": {
                "Type": "Task",
                "Resource": self.lambda_arn_prefix + "run_task_" + self.lambda_type + self.lambda_suffix,
                "Retry": self.sfn_run_task_retry_conditions,
                "Next": "CheckTaskAwsem"
            },
            "CheckTaskAwsem": {
                "Type": "Task",
                "Resource": self.lambda_arn_prefix + "check_task_" + self.lambda_type + self.lambda_suffix,
                "Retry": self.sfn_check_task_retry_conditions,
                "Next": "UpdateFFMetaAwsem"
            },
            "UpdateFFMetaAwsem": {
                "Type": "Task",
                "Resource": self.lambda_arn_prefix + "update_ffmeta_" + self.lambda_type + self.lambda_suffix,
                "Retry": self.sfn_update_ff_meta_retry_conditions,
                "End": True
            }
        }
        return state_defs

    @property
    def description(self):
        return "Start a workflow run on awsem, track it " + \
            "update our metadata to reflect whats going on"

    @property
    def definition(self):
        return {
          "Comment": self.description,
          "StartAt": self.sfn_start_lambda,
          "States": self.sfn_state_defs
        }
