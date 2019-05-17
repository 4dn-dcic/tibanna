# -*- coding: utf-8 -*-

from tibanna import utils


def handler(event, context):
    env_name = event['env_name']
    sfn = event.get('step_function_name')
    if sfn:
        res = utils.run_workflow(event, env=env_name, sfn=sfn)
    else:
        res = utils.run_workflow(event, env=env_name)

    try:
        start = str(res['_tibanna']['response']['startDate'])
        res['_tibanna']['response']['startDate'] = start
    except:
        pass

    return res
