from tibanna.check_task import check_task
from tibanna.vars import AWS_REGION

config = {
    'function_name': 'check_task_awsem',
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': AWS_REGION,
    'runtime': 'python3.8',
    'role': 'tibanna_lambda_init_role',
    'description': 'check status of AWSEM run by interegating appropriate files on S3 ',
    'timeout': 300,
    'memory_size': 256
}


def handler(event, context):
    return check_task(event)
