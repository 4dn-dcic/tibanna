# -*- coding: utf-8 -*-

from core import utils


class StillRunningException(Exception):
    pass


def handler(event, context):
    '''
    somewhere in the event data should be a jobid
    '''
    # s3 bucket that stores the output
    bucket_name = event['args']['output_s3_bucket']
    s3 = utils.s3Utils(bucket_name, bucket_name, bucket_name)

    # info about the jobby job
    jobid = event['jobid']
    job_started = "%s.job_started" % jobid
    job_success = "%s.success" % jobid
    job_error = "%s.error" % jobid
    job_log = "%s.log" % jobid
    job_log_location = "https://s3.amazonaws.com/%s/%s" % (bucket_name, job_log)

    # check to see ensure this job has started else fail
    if not s3.does_key_exist(job_started):
        raise Exception("Failed to find any evidence that jobid %s ever started" % jobid)

    # check to see if job has error, report if so
    if s3.does_key_exist(job_error):
        raise Exception("Job encountered an error check log at %s" % job_log_location)

    # check to see if job has completed if not throw retry error
    if s3.does_key_exist(job_success):
        print("completed successfully")
        return
    else:
        raise StillRunningException("job %s still running" % jobid)
