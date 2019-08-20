from tibanna.vars import *
import os

SECRET = os.environ.get("SECRET", '')
S3_ENCRYPT_KEY = os.environ.get("S3_ENCRYPT_KEY", '')

# default step function name
TIBANNA_DEFAULT_STEP_FUNCTION_NAME = os.environ.get('TIBANNA_DEFAULT_STEP_FUNCTION_NAME', 'tibanna_pony')
AWS_REGION = os.environ.get('TIBANNA_AWS_REGION', 'us-east-1')
