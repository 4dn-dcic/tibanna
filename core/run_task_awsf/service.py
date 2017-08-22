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
    instance_type: EC2 instance type
    ebs_size: EBS storage size in GB
    ebs_type: EBS storage type (available values: gp2, io1, st1, sc1, standard (default: io1)
    ebs_iops: EBS storage IOPS
    s3_access_arn: IAM instance profile for S3 access
    ami_id: ID of AMI used for the instance - it should have docker daemon and
            cwl-runner (either toil or cwltools) installed
    password: password for ssh connection for user ec2-user
    EBS_optimized: Use this flag if the instance type is EBS-optimized (default: EBS-optimized)
    shutdown_min: Number of minutes before shutdown after the jobs are finished. (default now)
    copy_to_s3: Upload or copy the json file to S3 bucket json_bucket
    launch_instance: Launch instance based on the json file

    args:
    cwl: main cwl file name
    cwl_children: names of the other cwl files used by main cwl file, delimiated by comma
    app_name: name of the app
    app_version: version of the app
    cwl_directory: the url and subdirectories for the main cwl file
    reference_S3_bucket: bucket name and subdirectory for input reference files
    output_S3_bucket: bucket name and subdirectory for output files and logs
    input_files: input files in json format (parametername:filename)
    secondary_files: secondary files in json format (parametername:filename)
    input_reference_files: input reference files in json format (parametername:filename)
    input_parameters: input parameters in json format (parametername:value)
    input_files_directory: bucket name and subdirectory for input files
    '''

    # read default variables in config
    CONFIG_FIELD = "config"
    CONFIG_KEYS = ["s3_access_arn", "EBS_optimized", "shutdown_min", "copy_to_s3",
                   "ami_id", "instance_type", "ebs_size", "launch_instance",
                   "ebs_type", "ebs_iops", "json_bucket", "password"]
    ARGS_FIELD = "args"
    ARGS_KEYS = ["cwl", "cwl_children", "app_name", "app_version", "input_files",
                 "reference_S3_bucket", "output_S3_bucket", "cwl_directory",
                 "input_reference_files", "input_parameters", "input_files_directory",
                 "secondary_files", "output_target"]

    cfg = event.get(CONFIG_FIELD)
    for k in CONFIG_KEYS:
        assert(k in cfg)

    args = event.get(ARGS_FIELD)
    for k in ARGS_KEYS:
        assert(k in args)

    # args: parameters needed by the instance to run a workflow
    # cfg: parameters needed to launch an instance
    cfg['job_tag'] = args.get('app_name')
    cfg['outbucket'] = args.get('output_bucket')
    cfg['userdata_dir'] = '/tmp/userdata'

    # local directory in which the json file will be first created.
    cfg['json_dir'] = '/tmp/json'

    # create json and copy to s3
    jobid = utils.create_json(event, '')

    # launch instance and execute workflow
    if cfg.get('launch_instance'):
        utils.launch_instance(cfg, jobid)

    return ({'args': args, 'config': cfg, 'jobid': jobid})
