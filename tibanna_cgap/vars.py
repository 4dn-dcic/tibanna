from tibanna_ffcommon.vars import *
import os


LAMBDA_TYPE = 'zebra'
ACCESSION_PREFIX = 'GAP'


# default step function name
TIBANNA_DEFAULT_STEP_FUNCTION_NAME = os.environ.get('TIBANNA_DEFAULT_STEP_FUNCTION_NAME', 'tibanna_' + LAMBDA_TYPE)


# fourfront
DEFAULT_INSTITUTION = '828cd4fe-ebb0-4b36-a94a-d2e3a36cc989'
DEFAULT_PROJECT = '12a92962-8265-4fc0-b2f8-cf14f05db58b'

HIGLASS_BUCKETS = []

IAM_BUCKETS = ['elasticbeanstalk-fourfront-cgap-wfoutput',
               'elasticbeanstalk-fourfront-cgap-files',
               'tibanna-output']
