from tibanna.core import (
    deploy_packaged_lambdas as _deploy_packaged_lambdas,
    deploy_tibanna
)
from . import lambdas as pony_lambdas  # over-write lambdas module
from .stepfunction import StepFunctionPony


def deploy_packaged_lambdas(name, tests=True, suffix=None,
                            dev=False, usergroup=None, lambdas_module=pony_lambdas):
    _deploy_packaged_lambdas(name, tests=tests, suffix=suffix,
                             dev=dev, usergroup=usergroup, lambdas_module=lambdas_module)


def deploy_pony(suffix=None, tests=True):
    deploy_tibanna(suffix=suffix, tests=tests,
                   lambdas_module=pony_lambdas, StepFunction=StepFunctionPony)
