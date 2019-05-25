from tibanna.exceptions import exception_coordinator
from tibanna.check_task import check_task

config = {
    'function_name': 'check_task_awsem',
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': 'us-east-1',
    'runtime': 'python3.6',
    'role': 'tibanna_lambda_init_role',
    'description': 'check status of AWSEM run by interegating appropriate files on S3 ',
    'timeout': 300,
    'memory_size': 256
}


def metadata_only(event):
    event.update({'postrunjson': 'metadata_only'})
    return event


@exception_coordinator('check_task_awsem', metadata_only)
def handler(event, context):
    return check_task(event)
