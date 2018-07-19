# -*- coding: utf-8 -*-

import boto3
from core.lambda_utils import (
    StillRunningException,
    EC2StartingException,
    AWSEMJobErrorException,
    powerup
)
import json


def metadata_only(event):
    event.update({'postrunjson': 'metadata_only'})
    return event


def read_s3(bucket, object):
    response = boto3.client('s3').get_object(Bucket=bucket, Key=object)
    LOG.info(str(response))
    return response['Body'].read()


def does_key_exist(bucket, object):
    try:
        file_metadata = boto3.client('s3').head_object(Bucket=bucket, Key=object)
    except Exception as e:
        print("object %s not found on bucket %s" % (str(key), str(bucket)))
        print(str(e))
        return False
    return file_metadata


@powerup('check_task_awsem', metadata_only)
def handler(event, context):
    '''
    somewhere in the event data should be a jobid
    '''
    RESPONSE_JSON_CONTENT_INCLUSION_LIMIT = 30000  # strictly it is 32,768 but just to be safe.

    # s3 bucket that stores the output
    bucket_name = event['config']['log_bucket']

    # info about the jobby job
    jobid = event['jobid']
    job_started = "%s.job_started" % jobid
    job_success = "%s.success" % jobid
    job_error = "%s.error" % jobid
    job_log = "%s.log" % jobid
    postrunjson = "%s.postrun.json" % jobid
    job_log_location = "https://s3.amazonaws.com/%s/%s" % (bucket_name, job_log)
    postrunjson_location = "https://s3.amazonaws.com/%s/%s" % (bucket_name, postrunjson)

    # check to see ensure this job has started else fail
    if not does_key_exist(bucket_name, job_started):
        raise EC2StartingException("Failed to find jobid %s, ec2 is probably still booting" % jobid)

    # check to see if job has error, report if so
    if does_key_exist(bucket_name, job_error):
        raise AWSEMJobErrorException("Job encountered an error check log at %s" % job_log_location)

    # check to see if job has completed if not throw retry error
    if does_key_exist(bucket_name, job_success):
        if not does_key_exist(bucket_name, postrunjson):
            raise Exception("Postrun json not found at %s" % postrunjson_location)
        postrunjsoncontent = json.loads(read_s3(postrunjson))
        if len(str(postrunjsoncontent)) + len(str(event)) < RESPONSE_JSON_CONTENT_INCLUSION_LIMIT:
            event['postrunjson'] = postrunjsoncontent
        else:
            event['postrunjson'] = {'log': 'postrun json not included due to data size limit',
                                    'Job': {'Output':  postrunjsoncontent['Job']['Output']}}
        print("completed successfully")
        return event
    else:
        raise StillRunningException("job %s still running" % jobid)
