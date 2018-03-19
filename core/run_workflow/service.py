# -*- coding: utf-8 -*-

from core import utils


def handler(event, context):
    env_name = event['env_name']
    workflow = event.get('step_function_name')
    if workflow:
        res = utils.run_workflow(event, env=env_name, workflow=workflow)
    else:
        res = utils.run_workflow(event, env=env_name)

    try:
        start = str(res['_tibanna']['response']['startDate'])
        res['_tibanna']['response']['startDate'] = start
    except:
        pass

    return res
