from tibanna.utils import powerup
from tibanna.run_task import run_task

config = {
    'function_name': 'run_task_awsem',
    'function_module': 'service',
    'function_handler': 'handler',
    'handler': 'service.handler',
    'region': 'us-east-1',
    'runtime': 'python3.6',
    'role': 'tibanna_lambda_init_role',
    'description': 'import files to SBG and create workflow object to store state of workflow run',
    'timeout': 300,
    'memory_size': 256
}


def metadata_only(event):
    event.update({'jobid': 'metadata_only'})
    return event


@powerup('run_task_awsem', metadata_only)
def handler(event, context):
    return run_task(event)
