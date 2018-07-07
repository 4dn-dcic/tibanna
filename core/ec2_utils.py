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
from dcicutils import s3_utils
import botocore.session
import boto3
from Benchmark import run as B

logger = logging.getLogger()
logger.setLevel(logging.INFO)

###########################################
# These utils exclusively live in Tibanna #
###########################################

AWS_ACCOUNT_NUMBER = os.environ.get('AWS_ACCOUNT_NUMBER')
AWS_S3_ROLE_NAME = os.environ.get('AWS_S3_ROLE_NAME')
S3_ACCESS_ARN = 'arn:aws:iam::' + AWS_ACCOUNT_NUMBER + ':instance-profile/' + AWS_S3_ROLE_NAME
print("S3_ACCESS_ARN = %s" % S3_ACCESS_ARN)


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
        if copy_to_s3 is True:
            runjson_file = "{jobid}.run.json".format(jobid=jobid)
            try:
                s3 = boto3.client('s3')
            except Exception:
                raise Exception("boto3 client error: Failed to upload run.json file {} to s3".format(runjson_file))
            try:
                s3.upload_file(json_dir + '/' + runjson_file, json_bucket, runjson_file)
            except Exception as e:
                raise Exception("file upload error: Failed to upload run.json file {} to s3 %s"
                                .format(runjson_file) % e)

    # print & retur JOBID
    print("jobid={}".format(jobid))
    return(jobid)


def create_run_workflow(jobid, shutdown_min,
                        script_url='https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/',
                        password='lalala',
                        json_bucket='4dn-aws-pipeline-run-json',
                        log_bucket='tibanna-output'):
    str = ''
    str += "#!/bin/bash\n"
    str += "JOBID={}\n".format(jobid)
    str += "RUN_SCRIPT=aws_run_workflow.sh\n"
    str += "SHUTDOWN_MIN={}\n".format(shutdown_min)
    str += "PASSWORD={}\n".format(password)
    str += "JSON_BUCKET_NAME={}\n".format(json_bucket)
    str += "LOGBUCKET={}\n".format(log_bucket)
    str += "SCRIPT_URL={}\n".format(script_url)
    str += "wget $SCRIPT_URL/$RUN_SCRIPT\n"
    str += "chmod +x $RUN_SCRIPT\n"
    str += "source $RUN_SCRIPT $JOBID $SHUTDOWN_MIN $JSON_BUCKET_NAME $LOGBUCKET $SCRIPT_URL $PASSWORD\n"
    print(str)
    return(str)


def launch_instance(par, jobid):

    # Create a userdata script to pass to the instance. The userdata script is run_workflow.$JOBID.sh.
    try:
        userdata_str = create_run_workflow(jobid, par['shutdown_min'], par['script_url'],
                                           par['password'], par['json_bucket'], par['log_bucket'])
    except Exception as e:
        raise Exception("Cannot create run_workflow script. %s" % e)

    # creating a launch command
    launch_args = {'ImageId': par['ami_id'],
                   'InstanceType': par['instance_type'],
                   'IamInstanceProfile': {'Arn': S3_ACCESS_ARN},
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

    if par['key_name']:
        launch_args.update({'KeyName': par['key_name']})

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


def update_config(config, app_name, input_files, parameters):

    if config['instance_type'] != '' and config['ebs_size'] != 0 and config['EBS_optimized'] != '':
        pass
    else:
        input_size_in_bytes = dict()
        for argname, f in input_files.iteritems():
            bucket = f['bucket_name']
            s3 = s3_utils.s3Utils(bucket, bucket, bucket)
            if isinstance(f['object_key'], list):
                size = []
                for key in f['object_key']:
                    try:
                        size.append(s3.get_file_size(key, bucket))
                    except:
                        raise Exception("Can't get input file size")
            else:
                try:
                    size = s3.get_file_size(f['object_key'], bucket)
                except:
                    raise Exception("Can't get input file size")
            input_size_in_bytes.update({str(argname): size})

        print({"input_size_in_bytes": input_size_in_bytes})
        try:
            res = B.benchmark(app_name, {'input_size_in_bytes': input_size_in_bytes, 'parameters': parameters})
        except:
            try:
                res
                raise Exception("Benchmarking not working. : {}".format(str(res)))
            except:
                raise Exception("Benchmarking not working. : None")

        if res is not None:
            logger.info(str(res))
            instance_type = res['aws']['recommended_instance_type']
            ebs_size = 10 if res['total_size_in_GB'] < 10 else int(res['total_size_in_GB']) + 1
            ebs_opt = res['aws']['EBS_optimized']

            if config['instance_type'] == '':
                config['instance_type'] = instance_type
            if config['ebs_size'] == 0:
                config['ebs_size'] = ebs_size
            if config['EBS_optimized'] == '':
                config['EBS_optimized'] = ebs_opt

        elif config['instance_type'] == '':
            raise Exception("instance type cannot be determined nor given")
        elif config['ebs_size'] == 0:
            raise Exception("ebs_size cannot be determined nor given")
        elif config['EBS_optimized'] == '':
            raise Exception("EBS_optimized cannot be determined nor given")


class WorkflowFile(object):

    def __init__(self, bucket, key, runner, accession=None, output_type=None,
                 filesize=None, md5=None):
        self.bucket = bucket
        self.key = key
        self.s3 = s3_utils.s3Utils(self.bucket, self.bucket, self.bucket)
        self.runner = runner
        self.accession = accession
        self.output_type = output_type
        self.filesize = filesize
        self.md5 = md5

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
        self.output_files_meta = json['ff_meta']['output_files']
        self.output_info = None
        if isinstance(json.get('postrunjson'), dict):
            self.output_info = json['postrunjson']['Job']['Output']['Output files']

    def output_files(self):
        files = dict()
        output_types = dict()
        for x in self.output_files_meta:
            output_types[x['workflow_argument_name']] = x['type']
        for k, v in self.args.get('output_target').iteritems():
            if k in output_types:
                out_type = output_types[k]
            else:
                out_type = None
            if out_type == 'Output processed file':
                file_name = v.split('/')[-1]
                accession = file_name.split('.')[0].strip('/')
            else:
                accession = None
            if self.output_info:
                md5 = self.output_info[k].get('md5sum', '')
                filesize = self.output_info[k].get('size', 0)
                wff = {k: WorkflowFile(self.output_s3, v, self, accession,
                                       output_type=out_type, filesize=filesize, md5=md5)}
            else:
                wff = {k: WorkflowFile(self.output_s3, v, self, accession,
                                       output_type=out_type)}
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

    def all_files(self):
        files = dict()
        files.update(self.input_files())
        files.update(self.output_files())
        return files

    @property
    def inputfile_accessions(self):
        return {k: v.accession for k, v in self.input_files().iteritems()}

    @property
    def all_file_accessions(self):
        return {k: v.accession for k, v in self.all_files().iteritems()}
