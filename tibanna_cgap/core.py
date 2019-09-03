from tibanna_ffcommon.core import API as _API
from .stepfunction import StepFunctionZebra
from .vars import TIBANNA_DEFAULT_STEP_FUNCTION_NAME, LAMBDA_TYPE


class API(_API):

    # This one cannot be imported in advance, because it causes circular import.
    # lambdas run_workflow / validate_md5_s3_initiator needs to import this API
    # to call run_workflow
    @property
    def lambdas_module(self):
        from . import lambdas as zebra_lambdas
        return zebra_lambdas

    @property
    def tibanna_packages(self):
        import tibanna
        import tibanna_cgap
        return [tibanna, tibanna_cgap]

    StepFunction = StepFunctionZebra
    default_stepfunction_name = TIBANNA_DEFAULT_STEP_FUNCTION_NAME
    default_env = 'fourfront-cgap'
    sfn_type = 'zebra'

    def __init__(self):
        pass

    def deploy_zebra(self, suffix=None, usergroup=None):
        self.deploy_tibanna(suffix=suffix, usergroup=usergroup)
