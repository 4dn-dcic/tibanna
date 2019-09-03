from tibanna.lambdas.run_task_awsem import handler as _handler, config
from tibanna_4dn.exceptions import exception_coordinator


config['function_name'] = 'run_task_pony'


def metadata_only(event):
    event.update({'jobid': 'metadata_only'})
    return event


@exception_coordinator('run_task_pony', metadata_only)
def handler(event, context):
    return _handler(event, context)
