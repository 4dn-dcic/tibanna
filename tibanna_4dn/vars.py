from tibanna.vars import *
import os


LAMBDA_TYPE = 'pony'
ACCESSION_PREFIX = '4DN'
S3_ENCRYPT_KEY = os.environ.get("S3_ENCRYPT_KEY", '')


# default step function name
TIBANNA_DEFAULT_STEP_FUNCTION_NAME = os.environ.get('TIBANNA_DEFAULT_STEP_FUNCTION_NAME', 'tibanna_' + LAMBDA_TYPE)


# fourfront
DEFAULT_AWARD = '1U01CA200059-01'
DEFAULT_LAB = '4dn-dcic-lab'

HIGLASS_BUCKETS = ['elasticbeanstalk-fourfront-webprod-wfoutput',
                   'elasticbeanstalk-fourfront-webdev-wfoutput']
