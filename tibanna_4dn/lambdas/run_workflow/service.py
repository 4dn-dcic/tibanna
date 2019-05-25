# -*- coding: utf-8 -*-

from tibanna.core import run_workflow
from tibanna.vars import TIBANNA_DEFAULT_STEP_FUNCTION_NAME


def handler(event, context):
    env_name = event['env_name']
    sfn = event.get('step_function_name', TIBANNA_DEFAULT_STEP_FUNCTION_NAME)
    res = run_workflow(event, env=env_name, sfn=sfn)

    try:
        start = str(res['_tibanna']['response']['startDate'])
        res['_tibanna']['response']['startDate'] = start
    except:
        pass

    return res
