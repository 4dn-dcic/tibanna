from tibanna.vars import *
import os


LAMBDA_TYPE = 'zebra'
ACCESSION_PREFIX = 'GAP'
S3_ENCRYPT_KEY = os.environ.get("S3_ENCRYPT_KEY", '')


# default step function name
TIBANNA_DEFAULT_STEP_FUNCTION_NAME = os.environ.get('TIBANNA_DEFAULT_STEP_FUNCTION_NAME', 'tibanna_' + LAMBDA_TYPE)
