from tibanna.core import API as _API
from .stepfunction import StepFunctionPony
from .vars import SECRET, TIBANNA_DEFAULT_STEP_FUNCTION_NAME
from tibanna.vars import AWS_REGION, AWS_ACCOUNT_NUMBER


class API(_API):

    # This one cannot be imported in advance, because it causes circular import.
    # lambdas run_workflow / validate_md5_s3_initiator needs to import this API
    # to call run_workflow
    @property
    def lambdas_module(self):
        from . import lambdas as pony_lambdas
        return pony_lambdas

    StepFunction = StepFunctionPony
    default_stepfunction_name = TIBANNA_DEFAULT_STEP_FUNCTION_NAME
    default_env = 'fourfront-webdev'
    sfn_type = 'pony'

    def __init__(self):
        pass

    def env_list(self, name):
        envlist = super().env_list(name)
        if envlist:
            return envlist
        envlist_pony = {
            'run_workflow': {'SECRET': SECRET,
                             'TIBANNA_AWS_REGION': AWS_REGION,
                             'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
            'start_run_awsem': {'SECRET': SECRET,
                                'TIBANNA_AWS_REGION': AWS_REGION,
                                'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
            'update_ffmeta_awsem': {'SECRET': SECRET,
                                    'TIBANNA_AWS_REGION': AWS_REGION,
                                    'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
            'validate_md5_s3_initiator': {'SECRET': SECRET,
                                          'TIBANNA_AWS_REGION': AWS_REGION,
                                          'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER}
        }
        return envlist_pony.get(name, '')

    def deploy_new(self, name, tests=True, suffix=None, dev=False, usergroup=None):
        """this one has tests=True by default"""
        super().deploy_new(name, tests=tests, suffix=suffix, dev=dev, usergroup=usergroup)

    def deploy_pony(self, suffix=None, tests=True):
        self.deploy_tibanna(suffix=suffix, tests=tests)
