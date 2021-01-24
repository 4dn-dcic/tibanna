# -*- coding: utf-8 -*-
import boto3
import json
import copy
from . import create_logger
from .cw_utils import TibannaResource
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from .utils import (
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
    MetricRetrievalException,
    AWSEMErrorHandler
)
from .vars import PARSE_AWSEM_TIME
from .core import API


RESPONSE_JSON_CONTENT_INCLUSION_LIMIT = 30000  # strictly it is 32,768 but just to be safe.


logger = create_logger(__name__)


def check_task(input_json):
    return CheckTask(input_json).run()


class CheckTask(object):
    TibannaResource = TibannaResource
    API = API

    def __init__(self, input_json):
        self.input_json = copy.deepcopy(input_json)

    def run(self):
        # s3 bucket that stores the output
        bucket_name = self.input_json['config']['log_bucket']
        instance_id = self.input_json['config'].get('instance_id', '')

        # info about the jobby job
        jobid = self.input_json['jobid']
        job_started = "%s.job_started" % jobid
        job_success = "%s.success" % jobid
        job_error = "%s.error" % jobid

        public_postrun_json = self.input_json['config'].get('public_postrun_json', False)

        # check to see ensure this job has started else fail
        if not does_key_exist(bucket_name, job_started):
            start_time = PARSE_AWSEM_TIME(self.input_json['config']['start_time'])
            now = datetime.now(tzutc())
            # terminate the instance if EC2 is not booting for more than 10 min.
            if start_time + timedelta(minutes=10) < now:
                try:
                    boto3.client('ec2').terminate_instances(InstanceIds=[instance_id])
                except:
                    pass  # most likely already terminated or never initiated
                raise EC2IdleException("Failed to find jobid %s, ec2 is not initializing for too long. Terminating the instance." % jobid)
            raise EC2StartingException("Failed to find jobid %s, ec2 is probably still booting" % jobid)

        # check to see if job has error, report if so
        if does_key_exist(bucket_name, job_error):
            try:
                self.handle_postrun_json(bucket_name, jobid, self.input_json, public_read=public_postrun_json)
            except Exception as e:
                logger.warning("error occurred while handling postrun json but continuing. %s" % str(e))
            eh = AWSEMErrorHandler()
            if 'custom_errors' in self.input_json['args']:
                eh.add_custom_errors(self.input_json['args']['custom_errors'])
            log = self.API().log(job_id=jobid, logbucket=bucket_name)
            ex = eh.parse_log(log)
            if ex:
                msg_aug = str(ex) + ". For more info - " + eh.general_awsem_check_log_msg(jobid)
                raise AWSEMJobErrorException(msg_aug)
            else:
                raise AWSEMJobErrorException(eh.general_awsem_error_msg(jobid))

        # check to see if job has completed
        if does_key_exist(bucket_name, job_success):
            self.handle_postrun_json(bucket_name, jobid, self.input_json, public_read=public_postrun_json)
            print("completed successfully")
            return self.input_json

        # checking if instance is terminated for no reason
        if instance_id:  # skip test for instance_id by not giving it to self.input_json
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
                    logger.error(errmsg)
                    raise EC2UnintendedTerminationException(errmsg)

            # check CPU utilization for the past hour
            filesystem = '/dev/nvme1n1'  # doesn't matter for cpu utilization
            end = datetime.now(tzutc())
            start = end - timedelta(hours=1)
            jobstart_time = boto3.client('s3').get_object(Bucket=bucket_name, Key=job_started).get('LastModified')
            if jobstart_time + timedelta(hours=1) < end:
                try:
                    cw_res = self.TibannaResource(instance_id, filesystem, start, end).as_dict()
                except Exception as e:
                    raise MetricRetrievalException(e)
                if 'max_cpu_utilization_percent' in cw_res:
                    self.terminate_idle_instance(jobid,
                                                 instance_id,
                                                 cw_res['max_cpu_utilization_percent'],
                                                 cw_res['max_ebs_read_bytes'])
        # if none of the above
        raise StillRunningException("job %s still running" % jobid)

    def terminate_idle_instance(self, jobid, instance_id, cpu, ebs_read):
        if not cpu or cpu < 1.0:
            # the instance wasn't terminated - otherwise it would have been captured in the previous error.
            if not ebs_read or ebs_read < 1000:  # minimum 1kb
                # in case the instance is copying files using <1% cpu for more than 1hr, do not terminate it.
                try:
                    boto3.client('ec2').terminate_instances(InstanceIds=[instance_id])
                    errmsg = (
                        "Nothing has been running for the past hour for job %s,"
                        "(CPU utilization %s and EBS read %s bytes)."
                    ) %  (jobid, str(cpu), str(ebs_read))
                    raise EC2IdleException(errmsg)
                except Exception as e:
                    errmsg = (
                        "Nothing has been running for the past hour for job %s,"
                        "but cannot terminate the instance - cpu utilization (%s) : %s"
                    ) %  (jobid, str(cpu), str(e))
                    logger.error(errmsg)
                    raise EC2IdleException(errmsg)

    def handle_postrun_json(self, bucket_name, jobid, input_json, public_read=False):
        postrunjson = "%s.postrun.json" % jobid
        if not does_key_exist(bucket_name, postrunjson):
            postrunjson_location = "https://s3.amazonaws.com/%s/%s" % (bucket_name, postrunjson)
            raise Exception("Postrun json not found at %s" % postrunjson_location)
        postrunjsoncontent = json.loads(read_s3(bucket_name, postrunjson))
        prj = AwsemPostRunJson(**postrunjsoncontent)
        prj.Job.update(instance_id=input_json['config'].get('instance_id', ''))
        self.handle_metrics(prj)
        logger.debug("inside funtion handle_postrun_json")
        logger.debug("content=\n" + json.dumps(prj.as_dict(), indent=4))
        # upload postrun json file back to s3
        acl = 'public-read' if public_read else 'private'
        try:
            boto3.client('s3').put_object(Bucket=bucket_name, Key=postrunjson, ACL=acl,
                                          Body=json.dumps(prj.as_dict(), indent=4).encode())
        except Exception as e:
            boto3.client('s3').put_object(Bucket=bucket_name, Key=postrunjson, ACL='private',
                                          Body=json.dumps(prj.as_dict(), indent=4).encode())
        except Exception as e:
            raise "error in updating postrunjson %s" % str(e)
        # add postrun json to the input json
        self.add_postrun_json(prj, input_json, RESPONSE_JSON_CONTENT_INCLUSION_LIMIT)

    def add_postrun_json(self, prj, input_json, limit):
        prjd = prj.as_dict()
        if len(str(prjd)) + len(str(input_json)) < limit:
            input_json['postrunjson'] = prjd
        else:
            if 'commands' in prjd:
                del prjd['commands']
            if len(str(prjd)) + len(str(input_json)) < limit:
                prjd['log'] = 'postrun json not included due to data size limit'
                input_json['postrunjson'] = prjd
            else:
                input_json['postrunjson'] = {'log': 'postrun json not included due to data size limit'}

    def handle_metrics(self, prj):
        try:
            resources = self.TibannaResource(prj.Job.instance_id,
                                             prj.Job.filesystem,
                                             prj.Job.start_time_as_str,
                                             prj.Job.end_time_as_str or datetime.now())
        except Exception as e:
            raise MetricRetrievalException("error getting metrics: %s" % str(e))
        prj.Job.update(Metrics=resources.as_dict())
        self.API().plot_metrics(prj.Job.JOBID, directory='/tmp/tibanna_metrics/',
                           force_upload=True, open_browser=False,
                           endtime=prj.Job.end_time_as_str or datetime.now(),
                           filesystem=prj.Job.filesystem,
                           instance_id=prj.Job.instance_id)
