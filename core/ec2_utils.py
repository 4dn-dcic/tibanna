#!/usr/bin/python
import json
import sys
import time
import random
import string
import os
import subprocess
import logging
# from invoke import run
import awscli.clidriver
from core import utils
import botocore.session

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# random string generator
def randomword(length):
    return ''.join(random.choice(string.lowercase+string.uppercase+string.digits) for i in range(length))


def create_jobid():
    return randomword(12)    # date+random_string


def get_start_time():
    return time.strftime("%Y%m%d-%H:%M:%S-%Z")


def create_json_filename(jobid, json_dir):
    return json_dir + '/' + jobid + '.run.json'


# run command and check the output
# return value is [True/False, output_string(stdout)]
# If the command failed, the first value will be False and the output string will be null.
def run_command_out_check(command):
    with open(os.devnull, 'w') as shutup:
        try:
            res = subprocess.check_output(command.split(" "), stderr=shutup)
            return([True, res])
        except subprocess.CalledProcessError:
            return([False, ''])


def launch_and_get_instance_id(launch_args, jobid):
    try:  # capturing stdout from the launch command
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'  # necessary? not sure just put it in there
        session = botocore.session.get_session()
        x = session.create_client('ec2')

    except Exception as e:
        raise Exception("Failed to create a client for EC2")
    try:
        res = 0
        res = x.run_instances(**launch_args)

    except Exception as e:
        raise Exception("failed to launch instance for job {jobid}: {log}. %s"
                        .format(jobid=jobid, log=res) % e)

    try:
        instance_id = res['Instances'][0]['InstanceId']
    except Exception as e:
        raise Exception("failed to retrieve instance ID for job {jobid}".format(jobid=jobid))

    return instance_id


def read_config(CONFIG_FILE, CONFIG_KEYS):

    # 1. read .workflow.config.json file and get some variables
    with open(CONFIG_FILE, 'r') as f:
        cfg = json.load(f)

    # checking all the necessary keys exist
    for k in CONFIG_KEYS:
        if k not in cfg:
            sys.exit("The config file doesn't have key {}".format(k))

    return cfg


def create_json(input_dict, jobid):
    # a is the final_args dictionary. json_dir is the output directory for the json file

    # create jobid here
    if not jobid:
        jobid = create_jobid()

    # start time
    start_time = get_start_time()

    a = input_dict.get('args')
    copy_to_s3 = input_dict.get('config').get('copy_to_s3')
    json_dir = input_dict.get('config').get('json_dir')
    json_bucket = input_dict.get('config').get('json_bucket')
    log_bucket = input_dict.get('config').get('log_bucket')

    # pre is a dictionary to be printed as a pre-run json file.
    pre = {'config': input_dict.get('config')}  # copy only config since arg is redundant with 'Job'
    pre.update({'Job': {'JOBID': jobid,
                        'App': {
                                 'App_name': a['app_name'],
                                 'App_version': a['app_version'],
                                 'cwl_url': a['cwl_directory_url'],
                                 'main_cwl': a['cwl_main_filename'],
                                 'other_cwl_files': ','.join(a['cwl_child_filenames'])
                        },
                        'Input': {
                                 'Input_files_data': {},    # fill in later (below)
                                 'Secondary_files_data': {},   # fill in later (below)
                                 'Input_files_reference': {},     # fill in later (below)
                                 'Input_parameters': a['input_parameters']
                        },
                        'Output': {
                                 'output_bucket_directory': a['output_S3_bucket'],
                                 'output_target': a['output_target'],
                                 'secondary_output_target': a['secondary_output_target']
                        },
                        'Log': {
                                 'log_bucket_directory': log_bucket
                        },
                        "start_time": start_time
                        }})

    # fill in input_files and input_reference_files (restructured)
    for item, value in a['input_files'].iteritems():
        pre['Job']['Input']['Input_files_data'][item] = {'class': 'File',
                                                         'dir': value.get('bucket_name'),
                                                         'path': value.get('object_key')}
    for item, value in a['secondary_files'].iteritems():
        pre['Job']['Input']['Secondary_files_data'][item] = {'class': 'File',
                                                             'dir': value.get('bucket_name'),
                                                             'path': value.get('object_key')}

    # writing to a json file
    json_filename = create_json_filename(jobid, json_dir)
    try:
        os.stat(json_dir)
    except:
        os.makedirs(json_dir)

    # write to new json file
    with open(json_filename, 'w') as json_new_f:
        json.dump(pre, json_new_f, indent=4, sort_keys=True)

    # Keep log of the final json
    logger.info(str(pre))

    # copy the json file to the s3 bucket
    logger.info(json_bucket)
    logger.info(copy_to_s3)

    if json_bucket:
        args = {'json_bucket': json_bucket, 'jobid': jobid, 'json_dir': json_dir}
        if copy_to_s3 is True:
            command = "s3 cp {json_dir}/{jobid}.run.json s3://{json_bucket}/{jobid}.run.json".format(**args)
            command_arr = command.encode('utf-8').split(' ')
            logger.info(command_arr)
            x = awscli.clidriver.create_clidriver()
            logger.info(x.main(command_arr))
            # subprocess.check_output(command, shell=True)

    # print & retur JOBID
    print("jobid={}".format(jobid))
    return(jobid)


def create_run_workflow(jobid, shutdown_min,
                        script_url='https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/',
                        password='lalala'):
    str = ''
    str += "#!/bin/bash\n"
    str += "JOBID={}\n".format(jobid)
    str += "RUN_SCRIPT=aws_run_workflow.sh\n"
    str += "SHUTDOWN_MIN={}\n".format(shutdown_min)
    str += "PASSWORD={}\n".format(password)
    str += "SCRIPT_URL={}\n".format(script_url)
    str += "wget $SCRIPT_URL/$RUN_SCRIPT\n"
    str += "chmod +x $RUN_SCRIPT\n"
    str += "source $RUN_SCRIPT $JOBID $SHUTDOWN_MIN $PASSWORD\n"
    return(str)


def launch_instance(par, jobid):

    # Create a userdata script to pass to the instance. The userdata script is run_workflow.$JOBID.sh.
    try:
        userdata_str = create_run_workflow(jobid, par['shutdown_min'], par['script_url'], par['password'])
    except Exception as e:
        raise Exception("Cannot create run_workflow script. %s" % e)

    # creating a launch command
    launch_args = {'ImageId': par['ami_id'],
                   'InstanceType': par['instance_type'],
                   'IamInstanceProfile': {'Arn': par['s3_access_arn']},
                   # 'UserData': 'file://' + Userdata_file,
                   'UserData': userdata_str,
                   'MaxCount': 1,
                   'MinCount': 1,
                   'InstanceInitiatedShutdownBehavior': 'terminate',
                   'DisableApiTermination': False,
                   'TagSpecifications': [{'ResourceType': 'instance',
                                          "Tags": [{"Key": "Name", "Value": "awsem-" + jobid},
                                                   {"Key": "Type", "Value": "awsem"}]}]
                   }

    # EBS options
    if par['EBS_optimized'] is True:
        launch_args.update({"EbsOptimized": True})

    launch_args.update({"BlockDeviceMappings": [{'DeviceName': '/dev/sdb',
                                                 'Ebs': {'DeleteOnTermination': True,
                                                         'VolumeSize': par['ebs_size'],
                                                         'VolumeType': par['ebs_type']}}]})
    if par['ebs_iops']:    # io1 type, specify iops
        launch_args["BlockDeviceMappings"][0]["Ebs"]['Iops'] = par['ebs_iops']

    instance_id = launch_and_get_instance_id(launch_args, jobid)

    # get public IP for the instance (This may not happen immediately)
    session = botocore.session.get_session()
    x = session.create_client('ec2')

    try_again = True
    while try_again:    # keep trying until you get the result.
        time.sleep(1)  # wait for one second before trying again.
        try:
            # sometimes you don't get a description immediately
            instance_desc_log = x.describe_instances(InstanceIds=[instance_id])
            instance_ip = instance_desc_log['Reservations'][0]['Instances'][0]['PublicIpAddress']
            try_again = False
        except:
            try_again = True

    return({'instance_id': instance_id, 'instance_ip': instance_ip, 'start_time': get_start_time()})


class WorkflowFile(object):

    def __init__(self, bucket, key, runner, accession=None):
        self.bucket = bucket
        self.key = key
        self.s3 = utils.s3Utils(self.bucket, self.bucket, self.bucket)
        self.runner = runner
        self.accession = accession

    @property
    def status(self):
        exists = self.s3.does_key_exist(self.key, self.bucket)
        if exists:
            return "COMPLETED"
        else:
            return "FAILED"

    def read(self):
        return self.s3.read_s3(self.key).strip()


# TODO: refactor this to inherit from an abstrat class called Runner
# then implement for SBG as well
class Awsem(object):

    def __init__(self, json):
        self.args = json['args']
        self.config = json['config']
        self.output_s3 = self.args['output_S3_bucket']
        self.app_name = self.args['app_name']

    def output_files(self):
        files = dict()
        for k, v in self.args.get('output_target').iteritems():
            wff = {k: WorkflowFile(self.output_s3, v, self)}
            files.update(wff)
        return files

    def secondary_output_files(self):
        files = dict()
        for k, v in self.args.get('secondary_output_target').iteritems():
            wff = {k: WorkflowFile(self.output_s3, v, self)}
            files.update(wff)
        return files

    def input_files(self):
        files = dict()
        for arg_name, item in self.args.get('input_files').iteritems():
            file_name = item.get('object_key').split('/')[-1]
            accession = file_name.split('.')[0].strip('/')
            wff = {arg_name: WorkflowFile(item.get('bucket_name'),
                                          item.get('object_key'),
                                          self,
                                          accession)}
            files.update(wff)
        return files

    @property
    def inputfile_accessions(self):
        return [v.accession for k, v in self.input_files().iteritems()]
