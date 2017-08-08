# -*- coding: utf-8 -*-

# import boto3
from core import ec2_utils as utils
# import json
# import random
# import sys
# import time
# import string
# import os
# import subprocess

# s3 = boto3.resource('s3')


def handler(event, context):
    '''
    config:
    cwl_url: the url and subdirectories for the main cwl file
    reference_S3_bucket: bucket name and subdirectory for input reference files
    output_S3_bucket: bucket name and subdirectory for output files and logs
    default_instance_type: EC2 instance type
    default_ebs_size: EBS storage size in GB
    default_ebs_type: EBS storage type (available values: gp2, io1, st1, sc1, standard (default: io1)
    ebs_iops: EBS storage IOPS
    json_dir: Local directory in which the output json file will be written
    s3_access_arn: IAM instance profile for S3 access
    worker_ami_id: ID of AMI used for the instance - it should have docker daemon and
                   cwl-runner (either toil or cwltools) installed
    userdata_dir: local directory to store userdata (used internally within lambda)
    keyname: keyname

    args:
    cwl: main cwl file name
    cwl_children: names of the other cwl files used by main cwl file, delimiated by comma
    app_name: name of the app
    app_version: version of the app
    input_files: input files in json format (parametername:filename)
    input_reference_files: input reference files in json format (parametername:filename)
    input_parameters: input parameters in json format (parametername:value)
    input_files_directory: bucket name and subdirectory for input files
    EBS_optimized: Use this flag if the instance type is EBS-optimized (default: EBS-optimized)
    shutdown_min: Number of minutes before shutdown after the jobs are finished. (default now)
    copy_to_s3: Upload or copy the json file to S3 bucket json_bucket
    launch_instance: Launch instance based on the json file
    '''

    # read default variables in config
    CONFIG_FIELD = "config"
    CONFIG_KEYS = ["reference_S3_bucket", "output_S3_bucket", "s3_access_arn",
                   "keyname", "worker_ami_id", "default_instance_type", "default_ebs_size",
                   "default_ebs_type", "ebs_iops", "userdata_dir", "json_dir", "cwl_url"]
    ARGS_FIELD = "args"
    ARGS_KEYS = ["cwl", "cwl_children", "app_name", "app_version", "input_files",
                 "input_reference_files", "input_parameters", "input_files_directory",
                 "EBS_optimized", "shutdown_min", "copy_to_s3", "launch_instance"]

    cfg = event.get(CONFIG_FIELD)
    for k in CONFIG_KEYS:
        assert(k in cfg)

    args = event.get(ARGS_FIELD)
    for k in ARGS_KEYS:
        assert(k in args)

    # parameters that will go into the pre-run json file
    final_args = {
     'cwl_directory': cfg.get('cwl_url'),
     'cwl': args.get('cwl'),
     'cwl_children': args.get('cwl_children'),
     'app_name': args.get('app_name'),
     'app_version': args.get('app_version'),
     'input_files': args.get('input_files'),
     'input_reference_files': args.get('input_reference_files'),
     'input_parameters': args.get('input_parameters'),
     'input_files_directory': args.get('input_files_directory'),
     'input_reference_files_directory': cfg.get('reference_S3_bucket'),
     'output_bucket_directory': cfg.get('output_S3_bucket'),
     'instance_type': cfg.get('default_instance_type'),
     'storage_size': cfg.get('default_ebs_size'),
     'storage_type': cfg.get('default_ebs_type'),
     'storage_iops': cfg.get('ebs_iops')
    }

    # parameters needed to launch an instance
    par = {
     'keyname': cfg.get('keyname'),
     's3_access_arn': cfg.get('s3_access_arn'),
     'worker_ami_id': cfg.get('worker_ami_id'),
     'userdata_dir': cfg.get('userdata_dir'),
     'instance_type': cfg.get('default_instance_type'),  # redundant with final_args
     'storage_size': cfg.get('default_ebs_size'),  # redundant with final_args
     'storage_type': cfg.get('default_ebs_type'),  # redundant with final_args
     'storage_iops': cfg.get('ebs_iops'),  # redundant with final_args
     'EBS_optimized': cfg.get('EBS_optimized'),
     'job_tag': final_args.get('app_name'),
     'outbucket': cfg.get('output_S3_bucket')  # redundant with output_bucket_directory in final_args
    }

    shutdown_min = args.get('shutdown_min')
    copy_to_s3 = args.get('copy_to_s3')

    # local directory in which the json file will be first created.
    json_dir = cfg.get('json_dir')

    # create json and copy to s3
    jobid = utils.create_json(final_args, json_dir, '', copy_to_s3)

    # launch instance and execute workflow
    if args.get('launch_instance'):
        utils.launch_instance(par, jobid, shutdown_min)
