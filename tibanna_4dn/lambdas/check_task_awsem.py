from tibanna.lambdas.check_task_awsem import handler as _handler, config
from tibanna_ffcommon.exceptions import exception_coordinator
from tibanna_4dn.vars import LAMBDA_TYPE


config['function_name'] = 'check_task_' + LAMBDA_TYPE


def metadata_only(event):
    event.update({'postrunjson': 'metadata_only'})
    return event


@exception_coordinator('check_task', metadata_only)
def handler(event, context):
    return _handler(event, context)
