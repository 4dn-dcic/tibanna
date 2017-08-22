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


def launch_and_get_instance_id(launch_command, jobid):
    logstr = ''
    try:  # capturing stdout from the launch command
        launch_command_arr = launch_command.split(' ')
        logger.info(launch_command)
        logger.info(str(launch_command_arr))
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
        x = awscli.clidriver.create_clidriver()
        logger.info(x.main(['s3', 'ls']))
        logger.info(x.main(launch_command_arr))
        # logs = run(launch_command)
        # logstr += logs.stdout
        # logstr += logs.stderr

    except Exception as e:
        raise Exception("failed to launch instance for job {jobid}: {log}. %s"
                        .format(jobid=jobid, log=logstr) % e)
    # log = json.loads(logstr)
    # return log['Instances'][0]['InstanceId']
    return 0


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

    # pre is a dictionary to be printed as a pre-run json file.
    pre = {'config': input_dict.get('config')}  # copy only config since arg is redundant with 'Job'
    pre.update({'Job': {'JOBID': jobid,
                        'App': {
                                 'App_name': a['app_name'],
                                 'App_version': a['app_version'],
                                 'cwl_url': a['cwl_directory'],
                                 'main_cwl': a['cwl'],
                                 'other_cwl_files': a['cwl_children']
                        },
                        'Input': {
                                 'Input_files_data': {},    # fill in later (below)
                                 'Secondary_files_data': {},   # fill in later (below)
                                 'Input_files_reference': {},     # fill in later (below)
                                 'Input_parameters': a['input_parameters']
                        },
                        'Output': {
                                 'output_bucket_directory': a['output_S3_bucket'],
                                 'output_target': a['output_target']
                        },
                        "start_time": start_time
                        }})

    # fill in input_files and input_reference_files (restructured)
    for item, value in a['input_files'].iteritems():
        pre['Job']['Input']['Input_files_data'][item] = {'class': 'File',
                                                         'dir': a['input_files_directory'],
                                                         'path': value}
    for item, value in a['secondary_files'].iteritems():
        pre['Job']['Input']['Secondary_files_data'][item] = {'class': 'File',
                                                             'dir': a['input_files_directory'],
                                                             'path': value}
    for item, value in a['input_reference_files'].iteritems():
        pre['Job']['Input']['Input_files_reference'][item] = {'class': 'File',
                                                              'dir': a['input_reference_files_directory'],
                                                              'path': value}

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


def create_run_workflow(jobid, userdata_dir, shutdown_min, password='lalala'):
    if not os.path.exists(userdata_dir):
        os.mkdir(userdata_dir)
    run_workflow_file = userdata_dir + '/run_workflow.' + jobid + '.sh'
    script_url = 'https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/'
    with open(run_workflow_file, 'w') as fout:
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
        fout.write(str)
    logger.info(str)
    # run_command_out_check("aws s3 cp {} s3://4dn-tool-evaluation-files/{}".format(run_workflow_file, 'mmm'))  # Soo


def launch_instance(par, jobid):

    # Create a userdata script to pass to the instance. The userdata script is run_workflow.$JOBID.sh.
    try:
        create_run_workflow(jobid, par['userdata_dir'], par['shutdown_min'], par['password'])
    except Exception as e:
        raise Exception("Cannot create run_workflow script. %s" % e)

    # creating a launch command
    Userdata_file = "{dir}/run_workflow.{jobid}.sh".format(jobid=jobid, dir=par['userdata_dir'])
    logger.info(Userdata_file)

    launch_args = {'ami': par['ami_id'],
                   'instance_type': par['instance_type'],
                   'arn': par['s3_access_arn'],
                   'userdata': 'file://' + Userdata_file,
                   }
    launch_command = "ec2 run-instances --image-id {ami} --instance-type {instance_type}" + \
                     " --instance-initiated-shutdown-behavior terminate --count 1 --enable-api-termination" + \
                     " --iam-instance-profile Arn={arn} --user-data={userdata}"
    launch_command = launch_command.format(**launch_args)
    if par['EBS_optimized'] is True:
        launch_command += " --ebs-optimized"

    # storage iops option
    if par['ebs_iops']:    # io1 type, specify iops
        options_ebs = " --block-device-mappings DeviceName=/dev/sdb,Ebs={{VolumeSize={EBS_SIZE}," + \
                          "VolumeType={EBS_TYPE},Iops={EBS_IOPS},DeleteOnTermination=true}}"
        options_ebs = options_ebs.format(EBS_SIZE=par['ebs_size'], EBS_TYPE=par['ebs_type'],
                                         EBS_IOPS=par['ebs_iops'])
    else:  # gp type or other type? do not specify iops
        options_ebs += " --block-device-mappings DeviceName=/dev/sdb,Ebs={{VolumeSize={EBS_SIZE}," + \
                       "VolumeType={EBS_TYPE},DeleteOnTermination=true}}"
        options_ebs = options_ebs.format(EBS_SIZE=par['ebs_size'], EBS_TYPE=par['ebs_type'])
    launch_command += options_ebs
    launch_command = launch_command.encode('utf-8')
    logger.info(launch_command)
    # launch_command_arr = launch_command.split(' ')
    # os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    # x = awscli.clidriver.create_clidriver()
    # x.main(launch_command_arr)

    # launch instance and get id
    # logger.info(launch_command)
    # logger.info(subprocess.check_output("aws s3 ls", shell=True))
    # logger.info(run('ls').stdout)
    # os.environ['PATH'] = os.environ['PATH'] + ":" + os.environ['LAMBDA_TASK_ROOT']

    # logger.info(run('/bin/echo $PATH; /bin/echo $LAMBDA_TASK_ROOT').stdout)
    # logger.info(run('/bin/ls -R /').stdout)
    # logger.info(run('/bin/ls').stdout)
    # logger.info(run('/bin/ls /usr/local/bin/').stdout)

    instance_id = launch_and_get_instance_id(launch_command, jobid)
    return(0)

    # get public IP for the instance (This may not happen immediately)
    instance_desc_command = "ec2 describe-instances --instance-id={instance_id}".format(instance_id=instance_id)
    instance_desc_command_arr = instance_desc_command.split(' ')
    x = awscli.clidriver.create_clidriver()
    x.main(instance_desc_command_arr)

    try_again = True
    while try_again:    # keep trying until you get the result.
        time.sleep(1)  # wait for one second before trying again.
        try:
            # sometimes you don't get a description immediately
            instance_desc_logstr = x.main(instance_desc_command_arr)
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
