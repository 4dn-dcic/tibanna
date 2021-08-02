from .vars import (
    AWS_REGION,
    AWS_ACCOUNT_NUMBER,
    SFN_TYPE,
    UPDATE_COST_LAMBDA_NAME
)
from .utils import create_tibanna_suffix


class StepFunctionCostUpdater(object):
    sfn_type = SFN_TYPE

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
        return create_tibanna_suffix(self.dev_suffix, self.usergroup)

    @property
    def lambda_arn_prefix(self):
        return "arn:aws:lambda:" + self.region_name + ":" + self.aws_acc + ":function:"

    @property
    def sfn_name(self):
        return 'tibanna_' + self.sfn_type + self.lambda_suffix + '_costupdater'

    @property
    def iam(self):
        from .iam_utils import IAM
        return IAM(self.usergroup)

    @property
    def sfn_role_arn(self):
        sfn_role_arn = "arn:aws:iam::" + self.aws_acc + ":role/" + \
                       self.iam.role_name('stepfunction')
        return sfn_role_arn

    @property
    def sfn_start_lambda(self):
        return 'Wait'

    @property
    def sfn_state_defs(self):
        state_defs = {
            "Wait": {
            "Type": "Wait",
            "Seconds": 43200, # Check every 12h
            "Next": "UpdateCostAwsem"
            },
            "UpdateCostAwsem": {
                "Type": "Task",
                "Resource": self.lambda_arn_prefix + UPDATE_COST_LAMBDA_NAME + self.lambda_suffix,
                "ResultPath": "$.done",
                "Next": "UpdateCostDone"
            },
            "UpdateCostDone": {
              "Type": "Choice",
              "Choices": [
                {
                  "Variable": "$.done.done",
                  "BooleanEquals": True,
                  "Next": "Done"
                }
              ],
              "Default": "Wait"
            },
            "Done": {
              "Type": "Pass",
              "End": True
            }
        }
        return state_defs

    @property
    def description(self):
        return "Update costs for a workflow run"

    @property
    def definition(self):
        return {
          "Comment": self.description,
          "StartAt": self.sfn_start_lambda,
          "States": self.sfn_state_defs
        }
