from tibanna.lambdas.run_task_awsem import handler as _handler, config as _config
from tibanna_4dn.exceptions import exception_coordinator


config = _config


def metadata_only(event):
    event.update({'jobid': 'metadata_only'})
    return event


@exception_coordinator('run_task_awsem', metadata_only)
def handler(event, context):
    return _handler(event)
