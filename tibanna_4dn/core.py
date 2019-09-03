from tibanna.core import API as _API
from .stepfunction import StepFunctionPony
from .vars import TIBANNA_DEFAULT_STEP_FUNCTION_NAME, LAMBDA_TYPE


class API(_API):

    # This one cannot be imported in advance, because it causes circular import.
    # lambdas run_workflow / validate_md5_s3_initiator needs to import this API
    # to call run_workflow
    @property
    def lambdas_module(self):
        from . import lambdas as pony_lambdas
        return pony_lambdas

    @property
    def tibanna_packages(self):
        import tibanna
        import tibanna_4dn
        return [tibanna, tibanna_4dn]

    StepFunction = StepFunctionPony
    default_stepfunction_name = TIBANNA_DEFAULT_STEP_FUNCTION_NAME
    default_env = 'fourfront-webdev'
    sfn_type = LAMBDA_TYPE

    def __init__(self):
        pass

    def deploy_pony(self, suffix=None, usergroup=None):
        self.deploy_tibanna(suffix=suffix, usergroup=usergroup)
