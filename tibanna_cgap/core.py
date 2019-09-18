from tibanna_ffcommon.core import API as _API
from .stepfunction import StepFunctionZebra
from .vars import TIBANNA_DEFAULT_STEP_FUNCTION_NAME, LAMBDA_TYPE, IAM_BUCKETS
from .cw_utils import TibannaResource


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
        import tibanna_ffcommon
        import tibanna_cgap
        return [tibanna, tibanna_ffcommon, tibanna_cgap]

    StepFunction = StepFunctionZebra
    default_stepfunction_name = TIBANNA_DEFAULT_STEP_FUNCTION_NAME
    default_env = 'fourfront-cgap'
    sfn_type = LAMBDA_TYPE
    lambda_type = LAMBDA_TYPE

    @property
    def TibannaResource(self):
        return TibannaResource

    def __init__(self):
        pass

    def deploy_zebra(self, suffix=None, usergroup='', setup=False):
        self.deploy_tibanna(suffix=suffix, usergroup=usergroup, setup=False,
                            buckets=','.join(IAM_BUCKETS))
