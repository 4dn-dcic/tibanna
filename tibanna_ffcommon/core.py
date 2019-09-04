from tibanna.core import API as _API
from .stepfunction import StepFunctionFFAbstract
from .vars import S3_ENCRYPT_KEY, TIBANNA_DEFAULT_STEP_FUNCTION_NAME


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
    sfn_type = ''  # fill in the actual type (e.g pony or zebra) for inherited class

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
            'start_run_' + self.sfn_type: {'S3_ENCRYPT_KEY': S3_ENCRYPT_KEY},
            'update_ffmeta_' + self.sfn_type: {'S3_ENCRYPT_KEY': S3_ENCRYPT_KEY},
            'validate_md5_s3_initiator_' + self.sfn_type: {'S3_ENCRYPT_KEY': S3_ENCRYPT_KEY},
            'validate_md5_s3_trigger_' + self.sfn_type: {}
        }
        return envlist_ff.get(name, '')
