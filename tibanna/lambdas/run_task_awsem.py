from tibanna.run_task import run_task
from tibanna.vars import AWS_REGION


config = {
    'function_name': 'run_task_awsem',
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': AWS_REGION,
    'runtime': 'python3.8',
    'role': 'tibanna_lambda_init_role',
    'description': 'launch an ec2 instance',
    'timeout': 300,
    'memory_size': 256
}


def handler(event, context):
    return run_task(event)
