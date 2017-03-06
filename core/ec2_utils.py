#!/usr/bin/python
import json
import sys
import time
import random
import string
import os
import subprocess
import argparse


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


def create_json(a, json_dir, jobid, copy_to_s3):
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
    print "launching an instance..."

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


# main
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--cwl", help="main cwl file name")
    parser.add_argument("-cd", "--cwl_directory",
                        help="the url and subdirectories for the main cwl file (override config)")
    parser.add_argument("-co", "--cwl_children",
                        help="names of the other cwl files used by main cwl file, delimiated by comma")
    parser.add_argument("-a", "--app_name", help="name of the app")
    parser.add_argument("-av", "--app_version", help="version of the app")
    parser.add_argument("-i", "--input_files", help="input files in json format (parametername:filename)")
    parser.add_argument("-ir", "--input_reference_files",
                        help="input reference files in json format (parametername:filename)")
    parser.add_argument("-ip", "--input_parameters", help="input parameters in json format (parametername:value)")
    parser.add_argument("-id", "--input_files_directory", help="bucket name and subdirectory for input files")
    parser.add_argument("-ird", "--input_reference_files_directory",
                        help="bucket name and subdirectory for input reference files (override config)")
    parser.add_argument("-o", "--output_bucket_directory",
                        help="bucket name and subdirectory for output files and logs (override config)")
    parser.add_argument("-t", "--instance_type", help="EC2 instance type (default set in config)")
    parser.add_argument("-s", "--storage_size", help="EBS storage size in GB (default set in config)")
    parser.add_argument("-sT", "--storage_type",
                        help="EBS storage type (available values: gp2, io1, st1, sc1, standard (default: io1)")
    parser.add_argument("-IO", "--storage_iops", help="EBS storage IOPS (default set in config)")
    parser.add_argument("-NO", "--not_EBS_optimized",
                        help="Use this flag if the instance type is not EBS-optimized (default: EBS-optimized)",
                        action="store_true")
    parser.add_argument("-jd", "--json_dir",
                        help="Local directory in which the output json file will be written (default set in config)")
    parser.add_argument("-J", "--job_id", help="Manually assign job ID as specififed (default: randomly generated)")
    parser.add_argument("-m", "--shutdown_min",
                        help="Number of minutes before shutdown after the jobs are finished. (default now)")
    parser.add_argument("-u", "--copy_to_s3",
                        help="Upload or copy the json file to S3 bucket json_bucket", action="store_true")
    parser.add_argument("-e", "--launch_instance", help="Launch instance based on the json file.", action="store_true")

    args = parser.parse_args()
    # default variables
    CONFIG_FILE = ".tibanna.config"
    CONFIG_KEYS = ["reference_S3_bucket", "output_S3_bucket", "s3_access_arn",
                   "keyname", "worker_ami_id", "default_instance_type", "default_ebs_size",
                   "default_ebs_type", "ebs_iops", "userdata_dir", "json_dir", "json_bucket",
                   "cwl_url", "job_list_file"]
    cfg = read_config(CONFIG_FILE, CONFIG_KEYS)

    # parameters that will go into the json file
    final_args = {
     'cwl': '',    # required
     'cwl_directory': cfg['cwl_url'],
     'cwl_children': [],
     'app_name': '',
     'app_version': '',
     'input_files': {},
     'input_reference_files': {},
     'input_parameters': {},
     'input_files_directory': '',  # required if input_files is not null
     'input_reference_files_directory': cfg['reference_S3_bucket'],
     'output_bucket_directory': cfg['output_S3_bucket'],
     'instance_type': cfg['default_instance_type'],
     'storage_size': cfg['default_ebs_size'],
     'storage_type': cfg['default_ebs_type'],
     'storage_iops': cfg['ebs_iops']
    }
    # local directory in which the json file will be first created.
    json_dir = cfg['json_dir']
    # bucket name to which the json file will be sent.
    json_bucket = cfg['json_bucket']

    # parameters needed to launch an instance
    par = {
     's3_access_arn': cfg['s3_access_arn'],
     'worker_ami_id': cfg['worker_ami_id'],
     'keyname': cfg['keyname'],
     'userdata_dir': cfg['userdata_dir'],
     'instance_type': cfg['default_instance_type'],  # redundant with final_args
     'storage_size': cfg['default_ebs_size'],  # redudant with final_args
     'storage_type': cfg['default_ebs_type'],  # redudant with final_args
     'storage_iops': cfg['ebs_iops'],  # redundant with final_args
     'EBS_optimized': True,
     'job_list_file': cfg['job_list_file'],
     'job_tag': '',  # app_name in final_args
     'outbucket': cfg['output_S3_bucket']  # redundant with output_bucket_directory in final_args
    }
    shutdown_min = 'now'

    if args.cwl:
        final_args['cwl'] = args.cwl
    else:
        sys.exit("cwl field is required")

    if args.cwl_directory:
        final_args['cwl_directory'] = args.cwl_directory

    if args.cwl_children:
        final_args['cwl_children'] = args.cwl_children.split(',')

    if args.app_name:
        final_args['app_name'] = args.app_name

    if args.app_version:
        final_args['app_version'] = args.app_version

    if args.input_files:
        print args.input_files  # debugging
        final_args['input_files'] = json.loads(args.input_files)

    if args.input_reference_files:
        final_args['input_reference_files'] = json.loads(args.input_reference_files)

    if args.input_parameters:
        final_args['input_parameters'] = json.loads(args.input_parameters)

    if args.input_files_directory:
        final_args['input_files_directory'] = args.input_files_directory
    elif bool(final_args['input_files']):
        sys.exit("input_files_directory must be provided if input_files is provided.")

    if args.input_reference_files_directory:
        final_args['input_reference_files_directory'] = args.input_reference_files_directory

    if args.output_bucket_directory:
        final_args['output_bucket_directory'] = args.output_bucket_directory

    if args.instance_type:
        final_args['instance_type'] = args.instance_type

    if args.storage_size:
        final_args['storage_size'] = int(args.storage_size)

    if args.storage_type:
        final_args['storage_type'] = args.storage_type

    if args.storage_iops:
        final_args['storage_iops'] = int(args.storage_iops)

    if args.not_EBS_optimized:
        par['EBS_optimized'] = False

    if args.json_dir:
        json_dir = args.json_dir

    if args.shutdown_min:
        shutdown_min = args.shutdown_min
    # make sure these parameters are consistent between par and a.
    par['instance_type'] = final_args['instance_type']
    par['storage_size'] = final_args['storage_size']
    par['storage_type'] = final_args['storage_type']
    par['storage_iops'] = final_args['storage_iops']
    par['job_tag'] = final_args['app_name']
    par['outbucket'] = final_args['output_bucket_directory']

    # EBS type
    if par['storage_type'] != 'io1':
        par['storage_iops'] = ''
        final_args['storage_iops'] = ''
    # create json and copy to s3
    jobid = create_json(final_args, json_dir, args.job_id, args.copy_to_s3)

    # launch instance and execute workflow
    if args.launch_instance:
        launch_instance(par, jobid, shutdown_min)
