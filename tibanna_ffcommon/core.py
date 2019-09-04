from tibanna.core import API as _API
from .stepfunction import StepFunctionFFAbstract
from .vars import S3_ENCRYPT_KEY, TIBANNA_DEFAULT_STEP_FUNCTION_NAME


class API(_API):

    @property
    def tibanna_packages(self):
        import tibanna
        import tibanna_ffcommon
        return [tibanna, tibanna_ffcommon]

    StepFunction = StepFunctionFFAbstract
    default_stepfunction_name = TIBANNA_DEFAULT_STEP_FUNCTION_NAME
    sfn_type = ''  # fill in the actual type (e.g pony or zebra) for inherited class

    @property
    def do_not_delete(self):
        return ['validate_md5_s3_trigger']

    def __init__(self):
        pass

    def env_list(self, name):
        envlist = super().env_list(name)
        if envlist:
            return envlist
        envlist_ff = {
            'run_workflow': {},
            'start_run': {'S3_ENCRYPT_KEY': S3_ENCRYPT_KEY},
            'update_ffmeta': {'S3_ENCRYPT_KEY': S3_ENCRYPT_KEY},
            'validate_md5_s3_initiator': {'S3_ENCRYPT_KEY': S3_ENCRYPT_KEY},
            'validate_md5_s3_trigger': {}
        }
        return envlist_ff.get(name, '')
