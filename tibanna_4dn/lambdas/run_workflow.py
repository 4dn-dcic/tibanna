# -*- coding: utf-8 -*-
from tibanna_4dn.core import API
from tibanna_4dn.vars import TIBANNA_DEFAULT_STEP_FUNCTION_NAME
from tibanna.vars import AWS_REGION


config = {
    'function_name': 'run_workflow',
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': AWS_REGION,
    'runtime': 'python3.6',
    'role': 'tibanna_lambda_init_role',
    'description': 'lambda that calls run_workflow',
    'timeout': 300,
    'memory_size': 256
}


def handler(event, context):
    env_name = event['env_name']
    sfn = event.get('step_function_name', TIBANNA_DEFAULT_STEP_FUNCTION_NAME)
    res = API().run_workflow(event, env=env_name, sfn=sfn)

    try:
        start = str(res['_tibanna']['response']['startDate'])
        res['_tibanna']['response']['startDate'] = start
    except:
        pass

    return res
