# -*- coding: utf-8 -*-

from core import utils


def handler(event, context):
    env_name = event['env_name']
    workflow = event.get('step_function_name')
    if workflow:
        return utils.run_workflow(event, env=env_name, workflow=workflow)
    else:
        return utils.run_workflow(event, env=env_name)
