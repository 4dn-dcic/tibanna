# -*- coding: utf-8 -*-
from .ec2_utils import Execution
from .vars import (
    TIBANNA_PROFILE_ACCESS_KEY,
    TIBANNA_PROFILE_SECRET_KEY
)


def run_task(input_json):
    '''
    config:
    # required
      instance_type: EC2 instance type
      ebs_size: EBS storage size in GB
      ebs_type: EBS storage type (available values: gp2, io1, st1, sc1, standard (default: io1)
      ebs_iops: EBS storage IOPS
      password: password for ssh connection for user ec2-user
      EBS_optimized: Use this flag if the instance type is EBS-optimized (default: EBS-optimized)
      shutdown_min: Number of minutes before shutdown after the jobs are finished. (default now)
      log_bucket: bucket for collecting logs (started, postrun, success, error, log)
    # optional
      public_postrun_json (optional): whether postrun json should be made public (default false)
      cloudwatch_dashboard (optional) : create a cloudwatch dashboard named awsem-<jobid>

    args:
    # required (i.e. field must exist):
      input_files: input files in json format (parametername: {'bucket_name':bucketname, 'object_key':filename})
      output_S3_bucket: bucket name and subdirectory for output files and logs
    # optional
      app_name: name of the app, used by Benchmark
      app_version: version of the app
      secondary_files: secondary files in json format (parametername: {'bucket_name':bucketnname, 'object_ke':filename})
      input_parameters: input parameters in json format (parametername:value)
      secondary_output_target: secondary output files in json format (similar to secondary_files)
    # required for cwl
      cwl_main_filename: main cwl file name
      cwl_directory_url: the url (http:// or s3://) in which the cwl files resides
      cwl_version: the version of cwl (now only 'v1' is supported)
      cwl_child_filenames (optional): names of the other cwl files used by main cwl file, delimited by comma
      language (optional for cwl): now only 'cwl_v1' is supported
    # required for wdl
      language: 'wdl' (='wdl_draft2'), 'wdl_v1', or 'wdl_draft2'
      wdl_main_filename: main wdl file name
      wdl_directory_url: the url (http:// or s3://) in which the wdl files resides
      wdl_child_filenames (optional): names of the other wdl files used by main wdl file, delimited by comma
    # required for snakemake
      language: 'snakemake'
      snakemake_main_filename: main snakemake file name
      snakemake_directory_url: the url (http:// or s3://) in which the snakemake files resides
      snakemake_child_filenames (optional): names of the other snakemake files, delimited by comma
    # optional
      dependency: {'exec_arn': [exec_arns]}
      spot_duration: 60  # block minutes 60-360 if requesting spot instance
    '''
    # profile
    if TIBANNA_PROFILE_ACCESS_KEY and TIBANNA_PROFILE_SECRET_KEY:
        profile = {'access_key': TIBANNA_PROFILE_ACCESS_KEY,
                   'secret_key': TIBANNA_PROFILE_SECRET_KEY}
    else:
        profile = None

    execution = Execution(input_json)
    execution.prelaunch(profile=profile)
    execution.launch()
    execution.postlaunch()
    return(execution.input_dict)
