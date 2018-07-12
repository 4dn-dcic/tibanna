# -*- coding: utf-8 -*-

from core import ec2_utils as utils
from core.utils import powerup
import os


def metadata_only(event):
    event.update({'jobid': 'metadata_only'})
    return event


@powerup('run_task_awsem', metadata_only)
def handler(event, context):
    '''
    config:
    instance_type: EC2 instance type
    ebs_size: EBS storage size in GB
    ebs_type: EBS storage type (available values: gp2, io1, st1, sc1, standard (default: io1)
    ebs_iops: EBS storage IOPS
    password: password for ssh connection for user ec2-user
    EBS_optimized: Use this flag if the instance type is EBS-optimized (default: EBS-optimized)
    shutdown_min: Number of minutes before shutdown after the jobs are finished. (default now)
    copy_to_s3: Upload or copy the json file to S3 bucket json_bucket
    launch_instance: Launch instance based on the json file
    log_bucket: bucket for collecting logs (started, postrun, success, error, log)
    public_postrun_json (optional): whether postrun json should be made public (default false)

    args:
    cwl_main_filename: main cwl file name
    cwl_child_filenames: names of the other cwl files used by main cwl file, delimiated by comma
    app_name: name of the app
    app_version: version of the app
    cwl_directory_url: the url and subdirectories for the main cwl file
    cwl_version: the version of cwl (either 'draft3' or 'v1')
    input_reference_files_directory: bucket name and subdirectory for input reference files
    output_S3_bucket: bucket name and subdirectory for output files and logs
    input_files: input files in json format (parametername: {'bucket_name':bucketname, 'object_key':filename})
    secondary_files: secondary files in json format (parametername: {'bucket_name':bucketnname, 'object_ke':filename})
    input_parameters: input parameters in json format (parametername:value)
    '''

    # read default variables in config
    CONFIG_FIELD = "config"
    CONFIG_KEYS = ["EBS_optimized", "shutdown_min", "copy_to_s3",
                   "instance_type", "ebs_size", "launch_instance", "key_name",
                   "ebs_type", "ebs_iops", "json_bucket", "password", "log_bucket"]
    ARGS_FIELD = "args"
    ARGS_KEYS = ["cwl_main_filename", "cwl_child_filenames", "app_name", "app_version",
                 "input_files", "output_S3_bucket", "cwl_directory_url",
                 "input_parameters", "secondary_files", "output_target", "secondary_output_target"]

    cfg = event.get(CONFIG_FIELD)
    for k in CONFIG_KEYS:
        assert k in cfg, "%s not in config_field" % k

    args = event.get(ARGS_FIELD)
    for k in ARGS_KEYS:
        assert k in args, "%s not in args field" % k

    # args: parameters needed by the instance to run a workflow
    # cfg: parameters needed to launch an instance
    cfg['job_tag'] = args.get('app_name')
    cfg['userdata_dir'] = '/tmp/userdata'

    # local directory in which the json file will be first created.
    cfg['json_dir'] = '/tmp/json'

    # postrun json should be made public? 
    if 'public_postrun_json' not in cfg:
        cfg['public_postrun_json'] = false  # 4dn will use 'true' --> this will automatically be added by start_run_awsem

    # AMI and script directory according to cwl version
    if args['cwl_version'] == 'v1':
        cfg['ami_id'] = os.environ.get('AMI_ID_CWL_V1')
        cfg['script_url'] = 'https://raw.githubusercontent.com/' + \
            os.environ.get('TIBANNA_REPO_NAME') + '/' + \
            os.environ.get('TIBANNA_REPO_BRANCH') + '/awsf_cwl_v1/'
    else:
        cfg['ami_id'] = os.environ.get('AMI_ID_CWL_DRAFT3')
        cfg['script_url'] = 'https://raw.githubusercontent.com/' + \
            os.environ.get('TIBANNA_REPO_NAME') + '/' + \
            os.environ.get('TIBANNA_REPO_BRANCH') + '/awsf_cwl_draft3/'

    utils.update_config(cfg, args['app_name'],
                        args['input_files'], args['input_parameters'])

    # create json and copy to s3
    jobid = utils.create_json(event, '')

    # launch instance and execute workflow
    if cfg.get('launch_instance'):
        launch_instance_log = utils.launch_instance(cfg, jobid)

    event.update({'jobid': jobid})
    event.update(launch_instance_log)
    return(event)
