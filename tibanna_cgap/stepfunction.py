from .vars import AWS_REGION, AWS_ACCOUNT_NUMBER
from tibanna_ffcommon.stepfunction import StepFunctionFFAbstract


class StepFunctionZebra(StepFunctionFFAbstract):

    @property
    def lambda_type(self):
        return 'zebra'
