#!/usr/bin/python
import json
import sys
import time
import os
import logging
# from invoke import run
import botocore.session
import boto3
from Benchmark import run as B
from core.utils import AWS_ACCOUNT_NUMBER, AWS_REGION
from core.utils import create_jobid
from core.utils import EC2LaunchException


logger = logging.getLogger()
logger.setLevel(logging.INFO)

###########################################
# These utils exclusively live in Tibanna #
###########################################

AWS_S3_ROLE_NAME = os.environ.get('AWS_S3_ROLE_NAME', '')
S3_ACCESS_ARN = 'arn:aws:iam::' + AWS_ACCOUNT_NUMBER + ':instance-profile/' + AWS_S3_ROLE_NAME


def get_start_time():
    return time.strftime("%Y%m%d-%H:%M:%S-%Z")


def create_json_filename(jobid, json_dir):
    return json_dir + '/' + jobid + '.run.json'


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


def create_json_dict(input_dict):
    # a is the final_args dictionary. json_dir is the output directory for the json file

    # create jobid here
    if 'jobid' in input_dict and input_dict.get('jobid'):
        jobid = input_dict.get('jobid')
    else:
        jobid = create_jobid()

    # start time
    start_time = get_start_time()

    a = input_dict.get('args')
    log_bucket = input_dict.get('config').get('log_bucket')

    # pre is a dictionary to be printed as a pre-run json file.
    pre = {'config': input_dict.get('config').copy()}  # copy only config since arg is redundant with 'Job'
    pre.update({'Job': {'JOBID': jobid,
                        'App': {
                                 'App_name': a['app_name'],
                                 'App_version': a['app_version'],
                                 'language': a.get('language', ''),
                                 'cwl_url': a.get('cwl_directory_url', ''),
                                 'main_cwl': a.get('cwl_main_filename', ''),
                                 'other_cwl_files': ','.join(a.get('cwl_child_filenames', [])),
                                 'wdl_url': a.get('wdl_directory_url', ''),
                                 'main_wdl': a.get('wdl_main_filename', ''),
                                 'other_wdl_files': ','.join(a.get('wdl_child_filenames', [])),
                        },
                        'Input': {
                                 'Input_files_data': {},    # fill in later (below)
                                 'Secondary_files_data': {},   # fill in later (below)
                                 'Input_parameters': a['input_parameters'],
                                 'Env': a.get('input_env', {})
                        },
                        'Output': {
                                 'output_bucket_directory': a['output_S3_bucket'],
                                 'output_target': a['output_target'],
                                 'alt_cond_output_argnames': a.get('alt_cond_output_argnames', []),
                                 'secondary_output_target': a['secondary_output_target']
                        },
                        'Log': {
                                 'log_bucket_directory': log_bucket
                        },
                        "start_time": start_time
                        }})

    # fill in input_files (restructured)
    for item, value in a['input_files'].iteritems():
        pre['Job']['Input']['Input_files_data'][item] = {'class': 'File',
                                                         'dir': value.get('bucket_name'),
                                                         'path': value.get('object_key'),
                                                         'rename': value.get('rename'),
                                                         'profile': value.get('profile', '')}
    for item, value in a['secondary_files'].iteritems():
        pre['Job']['Input']['Secondary_files_data'][item] = {'class': 'File',
                                                             'dir': value.get('bucket_name'),
                                                             'path': value.get('object_key'),
                                                             'rename': value.get('rename'),
                                                             'profile': value.get('profile', '')}

    # remove the password and keyname info
    if 'password' in pre['config']:
        del(pre['config']['password'])
    if 'key_name' in pre['config']:
        del(pre['config']['key_name'])

    return pre


def create_json(input_dict):
    json_dir = input_dict.get('config').get('json_dir')
    json_bucket = input_dict.get('config').get('json_bucket')
    pre = create_json_dict(input_dict)
    jobid = pre['Job']['JOBID']
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

    if json_bucket:
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
                        password='',
                        json_bucket='4dn-aws-pipeline-run-json',
                        log_bucket='tibanna-output',
                        language='cwl_draft3',  # cwl_v1, cwl_draft3
                        profile=None,
                        singularity=None):
    str = ''
    str += "#!/bin/bash\n"
    str += "JOBID={}\n".format(jobid)
    str += "RUN_SCRIPT=aws_run_workflow_" + language + ".sh\n"
    str += "SHUTDOWN_MIN={}\n".format(shutdown_min)
    str += "JSON_BUCKET_NAME={}\n".format(json_bucket)
    str += "LOGBUCKET={}\n".format(log_bucket)
    str += "SCRIPT_URL={}\n".format(script_url)
    str += "wget $SCRIPT_URL/$RUN_SCRIPT\n"
    str += "chmod +x $RUN_SCRIPT\n"
    str += "source $RUN_SCRIPT -i $JOBID -m $SHUTDOWN_MIN"
    str += " -j $JSON_BUCKET_NAME -l $LOGBUCKET -u $SCRIPT_URL"
    if password:
        str += " -p {}".format(password)
    if profile:
        str += " -a {access_key} -s {secret_key} -r {region}".format(region=AWS_REGION, **profile)
    if singularity:
        str += " -g"
    str += "\n"
    print(str)
    return(str)


def launch_instance(par, jobid, profile=None):
    '''profile is a dictionary { access_key: , secret_key: }'''
    # Create a userdata script to pass to the instance. The userdata script is run_workflow.$JOBID.sh.
    try:
        userdata_str = create_run_workflow(jobid, par['shutdown_min'], par['script_url'],
                                           par['password'], par['json_bucket'], par['log_bucket'],
                                           par.get('language', 'cwl_draft3'),
                                           profile,
                                           par.get('singularity', None))
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
                                                         'VolumeType': par['ebs_type']}},
                                                {'DeviceName': '/dev/sda1',
                                                 'Ebs': {'DeleteOnTermination': True,
                                                         'VolumeSize': 20,
                                                         'VolumeType': 'gp2'}}]})
    if par['ebs_iops']:    # io1 type, specify iops
        launch_args["BlockDeviceMappings"][0]["Ebs"]['Iops'] = par['ebs_iops']

    if par['ebs_size'] >= 16000:
        message = "EBS size limit (16TB) exceeded: (attempted size: %s)" % par['ebs_size']
        raise EC2LaunchException(message)

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
            if isinstance(f['object_key'], list):
                size = []
                for key in f['object_key']:
                    try:
                        size.append(get_file_size(key, bucket))
                    except:
                        raise Exception("Can't get input file size")
            else:
                try:
                    size = get_file_size(f['object_key'], bucket)
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


def get_file_size(key, bucket, size_in_gb=False):
        '''
        default returns file size in bytes,
        unless size_in_gb = True
        '''
        meta = does_key_exist(bucket, key)
        if not meta:
            raise Exception("key not found")
        one_gb = 1073741824
        size = meta['ContentLength']
        if size_in_gb:
            size = size / one_gb
        return size


def does_key_exist(bucket, object_name):
    try:
        file_metadata = boto3.client('s3').head_object(Bucket=bucket, Key=object_name)
    except Exception as e:
        print("object %s not found on bucket %s" % (str(object_name), str(bucket)))
        print(str(e))
        return False
    return file_metadata
