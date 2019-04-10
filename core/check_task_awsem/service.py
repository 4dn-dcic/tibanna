# -*- coding: utf-8 -*-

import boto3
from core.utils import (
    StillRunningException,
    EC2StartingException,
    AWSEMJobErrorException,
    EC2UnintendedTerminationException,
    EC2IdleException,
    powerup,
    printlog
)
import json
from core.ec2_utils import does_key_exist
from core.cw_utils import TibannaResource
from datetime import datetime, timedelta


RESPONSE_JSON_CONTENT_INCLUSION_LIMIT = 30000  # strictly it is 32,768 but just to be safe.


def metadata_only(event):
    event.update({'postrunjson': 'metadata_only'})
    return event


def read_s3(bucket, object_name):
    response = boto3.client('s3').get_object(Bucket=bucket, Key=object_name)
    printlog(str(response))
    return response['Body'].read()


@powerup('check_task_awsem', metadata_only)
def handler(event, context):
    '''
    somewhere in the event data should be a jobid
    '''

    # s3 bucket that stores the output
    bucket_name = event['config']['log_bucket']

    # info about the jobby job
    jobid = event['jobid']
    job_started = "%s.job_started" % jobid
    job_success = "%s.success" % jobid
    job_error = "%s.error" % jobid

    # check to see ensure this job has started else fail
    if not does_key_exist(bucket_name, job_started):
        raise EC2StartingException("Failed to find jobid %s, ec2 is probably still booting" % jobid)

    # check to see if job has error, report if so
    if does_key_exist(bucket_name, job_error):
        handle_postrun_json(bucket_name, jobid, event, False)
        raise AWSEMJobErrorException("Job encountered an error check log using invoke log --job-id=%s" % jobid)

    # check to see if job has completed
    if does_key_exist(bucket_name, job_success):
        handle_postrun_json(bucket_name, jobid, event)
        print("completed successfully")
        return event

    # checking if instance is terminated for no reason
    instance_id = event.get('instance_id', '')
    if instance_id:  # skip test for instance_id by not giving it to event
        try:
            res = boto3.client('ec2').describe_instances(InstanceIds=[instance_id])
        except Exception as e:
            if 'InvalidInstanceID.NotFound' in str(e):
                raise EC2UnintendedTerminationException("EC2 is no longer found for job %s - please rerun." % jobid)
            else:
                raise e
        if not res['Reservations']:
            raise EC2UnintendedTerminationException("EC2 is no longer found for job %s - please rerun." % jobid)
        else:
            ec2_state = res['Reservations'][0]['Instances'][0]['State']['Name']
            if ec2_state in ['stopped', 'shutting-down', 'terminated']:
                errmsg = "EC2 is terminated unintendedly for job %s - please rerun." % jobid
                printlog(errmsg)
                raise EC2UnintendedTerminationException(errmsg)

        # check CPU utilization for the past hour
        filesystem = '/dev/nvme1n1'  # doesn't matter for cpu utilization
        end = datetime.now()
        start = end - timedelta(hours=1)
        cw_res = TibannaResource(instance_id, filesystem, start, end).as_dict()
        if 'max_cpu_utilization_percent' in cw_res:
            if not cw_res['max_cpu_utilization_percent'] or cw_res['max_cpu_utilization_percent'] < 1.0:
                # the instance wasn't terminated - otherwise it would have been captured in the previous error.
                try:
                    boto3.client('ec2').terminate_instances(InstanceIds=[instance_id])
                except Exception as e:
                    errmsg = "Nothing has been running for the past hour for job %s," + \
                             "but cannot terminate the instance (cpu utilization (%s) : %s" % \
                             jobid, str(cw_res['max_cpu_utilization_percent']), str(e)
                    printlog(errmsg)
                raise EC2IdleException("Nothing has been running for the past hour for job%s - terminating." % jobid)

    # if none of the above
    raise StillRunningException("job %s still running" % jobid)


def handle_postrun_json(bucket_name, jobid, event, raise_error=True, filesystem=None):
    postrunjson = "%s.postrun.json" % jobid
    if not does_key_exist(bucket_name, postrunjson):
        if raise_error:
            postrunjson_location = "https://s3.amazonaws.com/%s/%s" % (bucket_name, postrunjson)
            raise Exception("Postrun json not found at %s" % postrunjson_location)
        return None
    postrunjsoncontent = json.loads(read_s3(bucket_name, postrunjson))
    if 'instance_id' in event:
        update_postrun_json(postrunjsoncontent, event['instance_id'], filesystem)
    printlog("inside funtion handle_postrun_json")
    printlog("content=\n" + json.dumps(postrunjsoncontent, indent=4))
    try:
        boto3.client('s3').put_object(Bucket=bucket_name, Key=postrunjson,
                                      Body=json.dumps(postrunjsoncontent, indent=4).encode())
    except Exception as e:
        raise "error in updating postrunjson %s" % str(e)
    add_postrun_json(postrunjsoncontent, event, RESPONSE_JSON_CONTENT_INCLUSION_LIMIT)


def add_postrun_json(postrunjsoncontent, event, limit):
    if len(str(postrunjsoncontent)) + len(str(event)) < limit:
        event['postrunjson'] = postrunjsoncontent
    else:
        event['postrunjson'] = {'log': 'postrun json not included due to data size limit',
                                'Job': {'Output':  postrunjsoncontent['Job']['Output']}}


def update_postrun_json(postrunjsoncontent, instance_id, filesystem=None):
    job = postrunjsoncontent.get('Job', '')
    if job:
        if 'start_time' in job:
            starttime = datetime.strptime(job['start_time'], '%Y%m%d-%H:%M:%S-UTC')
        else:
            return None
        if 'end_time' in job:
            endtime = datetime.strptime(job['end_time'], '%Y%m%d-%H:%M:%S-UTC')
        else:
            endtime = datetime.now()
        if 'filesystem' in job:
            filesystem = job['filesystem']
        elif not filesystem:
            return None
        job['instance_id'] = instance_id
        job['Metrics'] = TibannaResource(instance_id, filesystem, starttime, endtime).as_dict()
