#!/usr/bin/python
import json
import sys
import time
import random
import string
import os
import subprocess


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


def launch_and_get_instance_id(launch_command, jobid):
    try:  # capturing stdout from the launch command
        instance_launch_logstr = subprocess.check_output(launch_command, shell=True)
    except:
        sys.exit("failed to launch instance for job {jobid}".format(jobid=jobid))
    instance_launch_log = json.loads(instance_launch_logstr)
    return instance_launch_log['Instances'][0]['InstanceId']


def read_config(CONFIG_FILE, CONFIG_KEYS):

    # 1. read .workflow.config.json file and get some variables
    with open(CONFIG_FILE, 'r') as f:
        cfg = json.load(f)

    # checking all the necessary keys exist
    for k in CONFIG_KEYS:
        if k not in cfg:
            sys.exit("The config file doesn't have key {}".format(k))

    return cfg


def create_json(a, json_dir, jobid, copy_to_s3, json_bucket=''):
    # a is the final_args dictionary. json_dir is the output directory for the json file

    # create jobid here
    if not jobid:
        jobid = create_jobid()

    # start time
    start_time = get_start_time()

    #    pre is a dictionary to be printed as a pre-run json file.
    pre = {'JOBID': jobid,
           'App': {
                    'App_name': a['app_name'],
                    'App_version': a['app_version'],
                    'cwl_url': a['cwl_directory'],
                    'main_cwl': a['cwl'],
                    'other_cwl_files': a['cwl_children']
           },
           'Input': {
                    'Input_files_data': {},    # fill in later (below)
                    'Input_files_reference': {},     # fill in later (below)
                    'Input_parameters': a['input_parameters']
           },
           'Output': {
                    'output_bucket_directory': a['output_bucket_directory']
           },
           'Instance_type': a['instance_type'],
           'EBS_SIZE': a['storage_size'],
           'EBS_TYPE': a['storage_type'],
           'EBS_IOPS': a['storage_iops'],
           "AMI_ID": "ami-78c13615",
           "start_time": start_time
           }

    # fill in input_files and input_reference_files (restructured)
    for item, value in a['input_files'].iteritems():
        pre['Input']['Input_files_data'][item] = {'class': 'File', 'dir': a['input_files_directory'], 'path': value}
    for item, value in a['input_reference_files'].iteritems():
        pre['Input']['Input_files_reference'][item] = {'class': 'File',
                                                       'dir': a['input_reference_files_directory'],
                                                       'path': value}

    # wrap
    pre = {'Job': pre}

    # writing to a json file
    json_filename = create_json_filename(jobid, json_dir)
    try:
        os.stat(json_dir)
    except:
        os.makedirs(json_dir)

    # write to new json file
    with open(json_filename, 'w') as json_new_f:
        json.dump(pre, json_new_f, indent=4, sort_keys=True)

    # copy the json file to the s3 bucket
    if json_bucket:
        args = {'json_bucket': json_bucket, 'jobid': jobid, 'json_dir': json_dir}
        if copy_to_s3 is True:
            command = "aws s3 cp ./{json_dir}/{jobid}.run.json s3://{json_bucket}/{jobid}.run.json".format(**args)
            run_command_out_check(command)

    # print & retur JOBID
    print("jobid={}".format(jobid))
    return(jobid)


def launch_instance(par, jobid, shutdown_min):

    # Create a userdata script to pass to the instance. The userdata script is run_workflow.$JOBID.sh.
    args = {'jobid': jobid, 'dir': par['userdata_dir'], 'shotdown_min': shutdown_min}
    command = "./create_run_workflow.sh {jobid} {dir} {shutdown_min}".format(**args)
    run_command_out_check(command)

    # launch an instance
    print("launching an instance...")

    # creating a launch command
    Userdata_file = "{dir}/run_workflow.{jobid}.sh".format(jobid=jobid, dir=par['userdata_dir'])
    launch_args = {'ami': par['worker_ami_id'],
                   'instance_type': par['instance_type'],
                   'arn': par['s3_access_arn'],
                   'userdata': 'file://' + Userdata_file,
                   }
    launch_command = "aws ec2 run-instances --image-id {ami} --instance-type {instance_type}"
    " --instance-initiated-shutdown-behavior terminate --count 1 --enable-api-termination"
    " --iam-instance-profile Arn={arn} --user-data={userdata}".format(**launch_args)
    if par['keyname'] != '':
        launch_command += " --key-name {keyname}".format(keyname=par['keyname'])
    if par['EBS_optimized']:
        launch_command += " --ebs-optimized"
    if par['storage_iops']:    # io1 type, specify iops
        launch_command += " --block-device-mappings DeviceName=/dev/sdb, Ebs=\"{{VolumeSize={EBS_SIZE},"
        " VolumeType={EBS_TYPE}, Iops={EBS_IOPS}, DeleteOnTermination=true}"
        "}\"".format(EBS_SIZE=par['storage_size'], EBS_TYPE=par['storage_type'], EBS_IOPS=par['storage_iops'])
    else:  # gp type or other type? do not specify iops
        launch_command += " --block-device-mappings DeviceName=/dev/sdb,"
        "Ebs=\"{{VolumeSize={EBS_SIZE},"
        "VolumeType={EBS_TYPE}, DeleteOnTermination=true}}\"".format(EBS_SIZE=par['storage_size'],
                                                                     EBS_TYPE=par['storage_type'])

    # launch instance and get id
    instance_id = launch_and_get_instance_id(launch_command, jobid)

    # get public IP for the instance (This may not happen immediately)
    instance_desc_command = "aws ec2 describe-instances --instance-id={instance_id}".format(instance_id=instance_id)
    try_again = True
    while try_again:    # keep trying until you get the result.
        time.sleep(1)  # wait for one second before trying again.
        try:
            # sometimes you don't get a description immediately
            instance_desc_logstr = run_command_out_check(instance_desc_command)
            instance_desc_log = json.loads(instance_desc_logstr[1])
            # sometimes you get a description but PublicIP is not available yet
            instance_ip = instance_desc_log['Reservations'][0]['Instances'][0]['PublicIpAddress']
            try_again = False
        except:
            try_again = True

    print("instance_id={}, instance_ip={}".format(instance_id, instance_ip))
    # 5. Add to the job list
    with open(par['job_list_file'], 'a') as fo:
        fo.write("{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(jobid, instance_id,
                                                       par['instance_type'],
                                                       instance_ip, par['job_tag'],
                                                       get_start_time(), par['outbucket']))
