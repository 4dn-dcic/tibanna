from tibanna.core import API as _API
from .stepfunction import StepFunctionPony
from .vars import SECRET, TIBANNA_DEFAULT_STEP_FUNCTION_NAME
from .vars import LAMBDA_TYPE


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

    StepFunction = StepFunctionFFAbstract
    default_stepfunction_name = TIBANNA_DEFAULT_STEP_FUNCTION_NAME
    sfn_type = LAMBDA_TYPE

    @property
    def do_not_delete(self):
        return ['validate_md5_s3_trigger_' + self.sfn_type]

    def __init__(self):
        pass

    def env_list(self, name):
        envlist = super().env_list(name)
        if envlist:
            return envlist
        envlist_ff = {
            'run_workflow_' + self.sfn_type: {},
            'start_run_' + self.sfn_type: {'SECRET': SECRET},
            'update_ffmeta_' + self.sfn_type: {'SECRET': SECRET},
            'validate_md5_s3_initiator_' + self.sfn_type: {'SECRET': SECRET},
            'validate_md5_s3_trigger_' + self.sfn_type: {}
        }
        return envlist_ff.get(name, '')
