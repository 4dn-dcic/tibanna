from tibanna.lambdas.run_task_awsem import handler as _handler, config
from tibanna_ffcommon.exceptions import exception_coordinator
from tibanna_4dn.vars import LAMBDA_TYPE


config['function_name'] = 'run_task_' + LAMBDA_TYPE


def metadata_only(event):
    event.update({'jobid': 'metadata_only'})
    return event


@exception_coordinator('run_task', metadata_only)
def handler(event, context):
    return _handler(event, context)
