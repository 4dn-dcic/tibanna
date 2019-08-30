# -*- coding: utf-8 -*-
import boto3
import json
import copy
from .cw_utils import TibannaResource
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from .utils import (
    printlog,
    does_key_exist,
    read_s3
)
from .awsem import (
    AwsemPostRunJson
)
from .exceptions import (
    StillRunningException,
    EC2StartingException,
    AWSEMJobErrorException,
    EC2UnintendedTerminationException,
    EC2IdleException,
    MetricRetrievalException
)

RESPONSE_JSON_CONTENT_INCLUSION_LIMIT = 30000  # strictly it is 32,768 but just to be safe.


def check_task(input_json):
    '''
    somewhere in the input_json data should be a jobid
    '''
    input_json_copy = copy.deepcopy(input_json)

    # s3 bucket that stores the output
    bucket_name = input_json_copy['config']['log_bucket']

    # info about the jobby job
    jobid = input_json_copy['jobid']
    job_started = "%s.job_started" % jobid
    job_success = "%s.success" % jobid
    job_error = "%s.error" % jobid

    public_postrun_json = input_json_copy['config'].get('public_postrun_json', False)

    # check to see ensure this job has started else fail
    if not does_key_exist(bucket_name, job_started):
        raise EC2StartingException("Failed to find jobid %s, ec2 is probably still booting" % jobid)

    # check to see if job has error, report if so
    if does_key_exist(bucket_name, job_error):
        try:
            handle_postrun_json(bucket_name, jobid, input_json_copy, public_read=public_postrun_json)
        except Exception as e:
            printlog("error handling postrun json %s" % str(e))
        errmsg = "Job encountered an error check log using tibanna log --job-id=%s [--sfn=stepfunction]" % jobid
        raise AWSEMJobErrorException(errmsg)

    # check to see if job has completed
    if does_key_exist(bucket_name, job_success):
        handle_postrun_json(bucket_name, jobid, input_json_copy, public_read=public_postrun_json)
        print("completed successfully")
        return input_json_copy

    # checking if instance is terminated for no reason
    instance_id = input_json_copy.get('instance_id', '')
    if instance_id:  # skip test for instance_id by not giving it to input_json_copy
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
        end = datetime.now(tzutc())
        start = end - timedelta(hours=1)
        jobstart_time = boto3.client('s3').get_object(Bucket=bucket_name, Key=job_started).get('LastModified')
        if jobstart_time + timedelta(hours=1) < end:
            try:
                cw_res = TibannaResource(instance_id, filesystem, start, end).as_dict()
            except Exception as e:
                raise MetricRetrievalException(e)
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
                        raise EC2IdleException(errmsg)

    # if none of the above
    raise StillRunningException("job %s still running" % jobid)


def handle_postrun_json(bucket_name, jobid, input_json, public_read=False):
    postrunjson = "%s.postrun.json" % jobid
    if not does_key_exist(bucket_name, postrunjson):
        postrunjson_location = "https://s3.amazonaws.com/%s/%s" % (bucket_name, postrunjson)
        raise Exception("Postrun json not found at %s" % postrunjson_location)
    postrunjsoncontent = json.loads(read_s3(bucket_name, postrunjson))
    prj = AwsemPostRunJson(**postrunjsoncontent)
    prj.Job.update(instance_id=input_json['config'].get('instance_id', ''))
    handle_metrics(prj)
    printlog("inside funtion handle_postrun_json")
    printlog("content=\n" + json.dumps(prj.as_dict(), indent=4))
    # upload postrun json file back to s3
    acl = 'public-read' if public_read else 'private'
    try:
        boto3.client('s3').put_object(Bucket=bucket_name, Key=postrunjson, ACL=acl,
                                      Body=json.dumps(prj.as_dict(), indent=4).encode())
    except Exception as e:
        raise "error in updating postrunjson %s" % str(e)
    # add postrun json to the input json
    add_postrun_json(prj, input_json, RESPONSE_JSON_CONTENT_INCLUSION_LIMIT)


def add_postrun_json(prj, input_json, limit):
    prjd = prj.as_dict()
    if len(str(prjd)) + len(str(input_json)) < limit:
        input_json['postrunjson'] = prjd
    else:
        del prjd['commands']
        if len(str(prjd)) + len(str(input_json)) < limit:
            prjd['log'] = 'postrun json not included due to data size limit'
            input_json['postrunjson'] = prjd
        else:
            input_json['postrunjson'] = {'log': 'postrun json not included due to data size limit'}


def handle_metrics(prj):
    try:
        resources = TibannaResource(prj.Job.instance_id,
                                    prj.Job.filesystem,
                                    prj.Job.start_time_as_str,
                                    prj.Job.end_time_as_str or datetime.now())
    except Exception as e:
        raise MetricRetrievalException("error getting metrics: %s" % str(e))
    prj.Job.update(Metrics=resources.as_dict())
    resources.plot_metrics(prj.config.instance_type, directory='/tmp/tibanna_metrics/')
    resources.upload(bucket=prj.config.log_bucket, prefix=prj.Job.JOBID + '.metrics/')
