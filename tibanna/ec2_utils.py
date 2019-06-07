#!/usr/bin/python
import json
import sys
import time
import os
import logging
import botocore.session
import boto3
from .utils import (
    printlog,
    does_key_exist,
    create_jobid
)
from .vars import (
    AWS_REGION,
    S3_ACCESS_ARN,
    TIBANNA_REPO_NAME,
    TIBANNA_REPO_BRANCH,
    AMI_ID_WDL,
    AMI_ID_SHELL,
    AMI_ID_SNAKEMAKE,
    AMI_ID_CWL_V1,
    AMI_ID_CWL_DRAFT3
)
from .exceptions import (
    EC2LaunchException,
    EC2InstanceLimitException,
    EC2InstanceLimitWaitException
)
from .nnested_array import flatten, run_on_nested_arrays1
from Benchmark import run as B
logger = logging.getLogger()
logger.setLevel(logging.INFO)
NONSPOT_EC2_PARAM_LIST = ['TagSpecifications', 'InstanceInitiatedShutdownBehavior',
                          'MaxCount', 'MinCount', 'DisableApiTermination']
class Launch(object):

    def __init__(self, input_dict):
        if 'jobid' in input_dict and input_dict.get('jobid'):
            self.jobid = input_dict.get('jobid')
        else:
            self.jobid = create_jobid()
        self.args = input_dict.get('args')
        self.cfg = input_dict.get('config')
        self.auto_fill_input_json(self.args, self.cfg)
        self.user_specified_instance_type = self.cfg.get('instance_type', '')
        self.user_specified_EBS_optimized = self.cfg.get('EBS_optimized', '')
        self.benchmark = get_benchmarking()
        self.init_instance_type_list()
        self.update_config_instance_type()


    @static
    def auto_fill_input_json(args, cfg):
        # args: parameters needed by the instance to run a workflow
        # cfg: parameters needed to launch an instance
        if "ebs_size" not in cfg:
            cfg["ebs_size"] = 0
        if "ebs_type" not in cfg:
            cfg['ebs_type'] = 'gp2'
        if "ebs_iops" not in cfg:
            cfg['ebs_iops'] = ''
        if "shutdown_min" not in cfg:
            cfg['shutdown_min'] = 'now'
        if 'password' not in cfg:
            cfg['password'] = ''
        if 'key_name' not in cfg:
            cfg['key_name'] = ''
        cfg['job_tag'] = args.get('app_name', '')
        cfg['userdata_dir'] = '/tmp/userdata'
        # local directory in which the json file will be first created.
        cfg['json_dir'] = '/tmp/json'
        # postrun json should be made public?
        if 'public_postrun_json' not in cfg:
            cfg['public_postrun_json'] = False
            # 4dn will use 'true' --> this will automatically be added by start_run_awsem
        # script url
        cfg['script_url'] = 'https://raw.githubusercontent.com/' + \
            TIBANNA_REPO_NAME + '/' + TIBANNA_REPO_BRANCH + '/awsf/'
        # AMI and script directory according to cwl version
        if 'language' in args and args['language'] == 'wdl':
            cfg['ami_id'] = AMI_ID_WDL
        elif 'language' in args and args['language'] == 'shell':
            cfg['ami_id'] = AMI_ID_SHELL
        elif 'language' in args and args['language'] == 'snakemake':
            cfg['ami_id'] = AMI_ID_SNAKEMAKE
        else:
            if args['cwl_version'] == 'v1':
                cfg['ami_id'] = AMI_ID_CWL_V1
                args['language'] = 'cwl_v1'
            else:
                cfg['ami_id'] = AMI_ID_CWL_DRAFT3
                args['language'] = 'cwl_draft3'
            if args.get('singularity', False):
                cfg['singularity'] = True
        cfg['json_bucket'] = cfg['log_bucket']
        cfg['language'] = args['language']

    def init_instance_type_list(self):
        instance_type = self.user_specified_instance_type
        mem = self.cfg.get('mem', '')
        cpu = self.cfg.get('cpu', '')
        instance_type_dlist = []
        # user directly specified instance type
        if instance_type:
            instance_type_dlist.append(instance_type)
        # user specified mem and cpu
        if mem and cpu:
            list0 = get_instance_types(mem, cpu, exclude_t=False)
            nonredundant_list = [i for i in list0 if i['instance_type'] != instance_type]
            instance_type_dlist.extend(nonredundant_list)
        # user specifically wanted EBS_optimized instances
        if self.user_specified_EBS_optimized:
            instance_type_dlist = [i for i in instance_type_dlist if i['EBS_optimized']]
        # add benchmark only if there is no user specification
        if len(instance_type_dlist) == 0 and self.benchmark['instance_type']:
            instance_type_dlist.append(self.benchmark)
        self.instance_type_list = [i['instance_type'] for i in instance_type_dlist]
        self.instance_type_info = {i['instance_type']: i for i in instance_type_dlist}
        self.instance_type_index = 0  # choose the first one initially

    @property
    def instance_type(self):
        if len(self.instance_type_list) > self.instance_type_index:
            return self.instance_type_list[self.instance_type_index]
        else:
            return ''

    @property
    def EBS_optimized(self):
        if self.instance_type:
            return self.instance_type_info[self.instance_type]['EBS_optimized']
        else:
            return ''

    def choose_next_instance_type(self):
        self.instance_type_index += 1
        if len(self.instance_type_list) <= self.instance_type_index:
            raise Exception("No more instance type available that matches the criteria")

    def update_config_instance_type(self):
        # deal with missing fields
        self.cfg["instance_type"] = self.instance_type
        if not self.user_specified_EBS_optimized:
            self.cfg["EBS_optimized"] = self.EBS_optimized

    def get_benchmarking(self):
        """add instance_type, ebs_size, EBS_optimized info based on benchmarking.
        user-specified values overwrite the benchmarking.
        """
        app_name = self.cfg.get('app_name', '')
        input_files = self.args.get('input_files', {})
        parameters = self.args.get('parameters')
        input_size_in_bytes = dict()
        for argname, f in iter(input_files.items()):
            bucket = f['bucket_name']
            if isinstance(f['object_key'], list):
                size = flatten(run_on_nested_arrays1(f['object_key'],
                                                     get_file_size,
                                                     **{'bucket': bucket}))
            else:
                size = get_file_size(f['object_key'], bucket)
            input_size_in_bytes.update({str(argname): size})
        print({"input_size_in_bytes": input_size_in_bytes})
        if not app_name:
            err_msg = "app_name must be provided to use Benchmarking." + \
                      "Without app_name, instance_type, ebs_size and EBS_optimized must be" + \
                      "in the config field of the execution json."
            raise Exception(err_msg)
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
            return {'instance_type: instance_type, 'EBS_optimized': ebs_opt, 'ebs_size': ebs_size}
        else:
            return {'instance_type: '', 'EBS_optimized': '', 'ebs_size': 0}

    @static
    def get_start_time():
        return time.strftime("%Y%m%d-%H:%M:%S-%Z")

    def launch_and_get_instance_id(self)
        try:  # capturing stdout from the launch command
            os.environ['AWS_DEFAULT_REGION'] = AWS_REGION
            ec2 = boto3.client('ec2')
        except Exception as e:
            raise Exception("Failed to create a client for EC2")
        if self.cfg.get('spot_instance', ''):
            spot_options = {'SpotInstanceType': 'one-time',
                            'InstanceInterruptionBehavior': 'terminate'}
            if self.cfg.get('spot_duration, ''):
                spot_options['BlockDurationMinutes'] = self.cfg.spot_duration
            self.launch_args.update({'InstanceMarketOptions': {'MarketType': 'spot',
                                                               'SpotOptions': spot_options}})
        try:
            res = 0
            res = ec2.run_instances(**self.launch_args)
        except Exception as e:
            if 'InsufficientInstanceCapacity' in str(e) or 'InstanceLimitExceeded' in str(e):
                behavior = self.cfg.get('behavior_on_capacity_limit', '')
                if behavior == 'fail':
                    errmsg = "Instance limit exception - use 'behavior_on_capacity_limit' option"
                    errmsg += "to change the behavior to wait_and_retry, or retry_without_spot. %s" % str(e)
                    raise EC2InstanceLimitException(errmsg)
                elif behavior == 'wait_and_retry':
                    errmsg = "Instance limit exception - wait and retry later: %s" % str(e)
                    raise EC2InstanceLimitWaitException(errmsg)
                elif behavior == 'retry_without_spot':
                    if not self.cfg.spot_instance:
                        errmsg = "'behavior_on_capacity_limit': 'retry_without_spot' works only with"
                        errmsg += "'spot_instance' : true. %s" % str(e)
                        raise Exception(errmsg)
                    del(self.launch_args['InstanceMarketOptions'])
                    try:
                        res = ec2.run_instances(**self.launch_args)
                        printlog("trying without spot : %s" % str(res))
                    except Exception as e2:
                        errmsg = "Instance limit exception without spot instance %s" % str(e2)
                        raise EC2InstanceLimitException(errmsg)
            else:
                raise Exception("failed to launch instance for job {jobid}: {log}. %s"
                                .format(jobid=self.jobid, log=res) % e)
        try:
            instance_id = res['Instances'][0]['InstanceId']
        except Exception as e:
            raise Exception("failed to retrieve instance ID for job {jobid}".format(jobid=self.jobid))
        return instance_id

    def create_json_dict(self):
        # a is the final_args dictionary. json_dir is the output directory for the json file
        # create jobid here
        # start time
        start_time = get_start_time()
        log_bucket = input_dict.get('config').get('log_bucket')
        # pre is a dictionary to be printed as a pre-run json file.
        pre = {'config': input_dict.get('config').copy()}  # copy only config since arg is redundant with 'Job'
        pre.update({'Job': {'JOBID': jobid,
                            'App': {
                                     'App_name': a.get('app_name', ''),
                                     'App_version': a.get('app_version', ''),
                                     'language': a.get('language', ''),
                                     'cwl_url': a.get('cwl_directory_url', ''),
                                     'main_cwl': a.get('cwl_main_filename', ''),
                                     'other_cwl_files': ','.join(a.get('cwl_child_filenames', [])),
                                     'wdl_url': a.get('wdl_directory_url', ''),
                                     'main_wdl': a.get('wdl_main_filename', ''),
                                     'other_wdl_files': ','.join(a.get('wdl_child_filenames', [])),
                                     'snakemake_url': a.get('snakemake_directory_url', ''),
                                     'main_snakemake': a.get('snakemake_main_filename', ''),
                                     'other_snakemake_files': ','.join(a.get('snakemake_child_filenames', [])),
                                     'command': a.get('command', ''),
                                     'container_image': a.get('container_image', '')
                            },
                            'Input': {
                                     'Input_files_data': {},    # fill in later (below)
                                     'Secondary_files_data': {},   # fill in later (below)
                                     'Input_parameters': a.get('input_parameters', {}),
                                     'Env': a.get('input_env', {})
                            },
                            'Output': {
                                     'output_bucket_directory': a['output_S3_bucket'],
                                     'output_target': a['output_target'],
                                     'alt_cond_output_argnames': a.get('alt_cond_output_argnames', []),
                                     'secondary_output_target': a.get('secondary_output_target', {})
                            },
                            'Log': {
                                     'log_bucket_directory': log_bucket
                            },
                            "start_time": start_time
                            }})
        # fill in input_files (restructured)
        for item, value in iter(a['input_files'].items()):
            pre['Job']['Input']['Input_files_data'][item] = {'class': 'File',
                                                             'dir': value.get('bucket_name'),
                                                             'path': value.get('object_key'),
                                                             'rename': value.get('rename'),
                                                             'profile': value.get('profile', '')}
        for item, value in iter(a.get('secondary_files', {}).items()):
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

    def create_json(self):
        pre = create_json_dict()
        jsonbody = json.dumps(pre, indent=4, sort_keys=True)
        jsonkey = self.jobid + '.run.json'
        # Keep log of the final json
        logger.info("jsonbody=\n" + jsonbody)
        # copy the json file to the s3 bucket
        logger.info("json_bucket = " + self.cfg['json_bucket'])
        if self.cfg['json_bucket']:
            try:
                s3 = boto3.client('s3')
            except Exception as e:
                raise Exception("boto3 client error: Failed to connect to s3 : %s" % str(e))
            try:
                res = s3.put_object(Body=jsonbody.encode('utf-8'), Bucket=self.cfg['json_bucket'], Key=jsonkey)
            except Exception:
                raise Exception("boto3 client error: Failed to upload run.json %s to s3: %s" % (jsonkey, str(res)))
        # print & retur JOBID
        print("jobid={}".format(self.jobid))
        return(self.jobid)

    def create_run_workflow(profile=None):
        str = ''
        str += "#!/bin/bash\n"
        str += "JOBID={}\n".format(self.jobid)
        str += "RUN_SCRIPT=aws_run_workflow_generic.sh\n"
        str += "SHUTDOWN_MIN={}\n".format(self.cfg[''shutdown_min'])
        str += "JSON_BUCKET_NAME={}\n".format(self.cfg['json_bucket'])
        str += "LOGBUCKET={}\n".format(self.cfg['log_bucket'])
        str += "SCRIPT_URL={}\n".format(self.cfg['script_url'])
        str += "LANGUAGE={}\n".format(self.cfg['language'])
        str += "wget $SCRIPT_URL/$RUN_SCRIPT\n"
        str += "chmod +x $RUN_SCRIPT\n"
        str += "source $RUN_SCRIPT -i $JOBID -m $SHUTDOWN_MIN"
        str += " -j $JSON_BUCKET_NAME -l $LOGBUCKET -u $SCRIPT_URL -L $LANGUAGE"
        if self.cfg['password']:
            str += " -p {}".format(self.cfg['password'])
        if profile:
            str += " -a {access_key} -s {secret_key} -r {region}".format(region=AWS_REGION, **profile)
        if self.cfg['singularity']:
            str += " -g"
        str += "\n"
        print(str)
        return(str)

    def create_launch_args(self):
        # creating a launch command
        launch_args = {'ImageId': self.cfg['ami_id'],
                       'InstanceType': self.cfg['instance_type'],
                       'IamInstanceProfile': {'Arn': S3_ACCESS_ARN},
                       'UserData': self.userdata_str,
                       'MaxCount': 1,
                       'MinCount': 1,
                       'InstanceInitiatedShutdownBehavior': 'terminate',
                       'DisableApiTermination': False,
                       'TagSpecifications': [{'ResourceType': 'instance',
                                              "Tags": [{"Key": "Name", "Value": "awsem-" + self.jobid},
                                                       {"Key": "Type", "Value": "awsem"}]}]
                       }
        if self.cfg['key_name']:
            launch_args.update({'KeyName': self.cfg['key_name']})
        # EBS options
        if self.cfg['EBS_optimized'] is True:
            launch_args.update({"EbsOptimized": True})
        launch_args.update({"BlockDeviceMappings": [{'DeviceName': '/dev/sdb',
                                                     'Ebs': {'DeleteOnTermination': True,
                                                             'VolumeSize': self.cfg['ebs_size'],
                                                             'VolumeType': self.cfg['ebs_type']}},
                                                    {'DeviceName': '/dev/sda1',
                                                     'Ebs': {'DeleteOnTermination': True,
                                                             'VolumeSize': 8,
                                                             'VolumeType': 'gp2'}}]})
        if self.cfg['ebs_iops']:    # io1 type, specify iops
            launch_args["BlockDeviceMappings"][0]["Ebs"]['Iops'] = self.cfg['ebs_iops']
        if self.cfg['ebs_size'] >= 16000:
            message = "EBS size limit (16TB) exceeded: (attempted size: %s)" % self.cfg['ebs_size']
            raise EC2LaunchException(message)
        return launch_args

    def launch_instance(self, profile=None):
        '''profile is a dictionary { access_key: , secret_key: }'''
        # Create a userdata script to pass to the instance. The userdata script is run_workflow.$JOBID.sh.
        try:
            userdata_str = create_run_workflow(self.jobid, self.cfg['shutdown_min'], self.cfg['script_url'],
                                               self.cfg['password'], self.cfg['json_bucket'], self.cfg['log_bucket'],
                                               self.cfg.get('language', 'cwl_draft3'),
                                               profile,
                                               self.cfg.get('singularity', None))
        except Exception as e:
            raise Exception("Cannot create run_workflow script. %s" % e)
        self.launch_args = self.create_launch_args()
        instance_id = self.launch_and_get_instance_id()
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

    def create_cloudwatch_dashboard(instance_id, dashboard_name):
        body = {
           "widgets": [
              {
                 "type": "metric",
                 "x": 0,
                 "y": 0,
                 "width": 12,
                 "height": 4,
                 "properties": {
                    "stacked":  True,
                    "metrics": [
                       [
                          "System/Linux",
                          "MemoryUsed",
                          "InstanceId",
                          instance_id
                       ],
                       [
                          ".",
                          "MemoryAvailable",
                          "InstanceId",
                          instance_id
                       ]
                    ],
                    "period": 60,
                    "stat": "Average",
                    "region": AWS_REGION,
                    "title": "Memory Used"
                 }
              },
              {
                 "type": "metric",
                 "x": 0,
                 "y": 5,
                 "width": 12,
                 "height": 4,
                 "properties": {
                    "metrics": [
                       [
                          "System/Linux",
                          "DiskSpaceUtilization",
                          "MountPath",
                          "/data1",
                          "InstanceId",
                          instance_id,
                          "Filesystem",
                          "/dev/xvdb"
                       ],
                       [
                          "System/Linux",
                          "DiskSpaceUtilization",
                          "MountPath",
                          "/",
                          "InstanceId",
                          instance_id,
                          "Filesystem",
                          "/dev/xvda1"
                       ]
                    ],
                    "period": 60,
                    "stat": "Average",
                    "region": AWS_REGION,
                    "title": "Disk Space Utilization"
                 }
              },
              {
                 "type": "metric",
                 "x": 0,
                 "y": 10,
                 "width": 12,
                 "height": 3,
                 "properties": {
                    "metrics": [
                       [
                          "System/Linux",
                          "DiskSpaceUsed",
                          "MountPath",
                          "/data1",
                          "InstanceId",
                          instance_id,
                          "Filesystem",
                          "/dev/xvdb"
                       ]
                    ],
                    "period": 60,
                    "stat": "Average",
                    "region": AWS_REGION,
                    "title": "Data Disk Space Used"
                 }
              },
              {
                 "type": "metric",
                 "x": 0,
                 "y": 13,
                 "width": 12,
                 "height": 3,
                 "properties": {
                    "metrics": [
                       [
                          "AWS/EC2",
                          "CPUUtilization",
                          "InstanceId",
                          instance_id
                       ]
                    ],
                    "period": 60,
                    "stat": "Average",
                    "region": AWS_REGION,
                    "title": "CPU Utilization"
                 }
              }
           ]
        }
        cw = boto3.client('cloudwatch', AWS_REGION)
        cw.put_dashboard(
            DashboardName=dashboard_name,
            DashboardBody=json.dumps(body)
        )

    def upload_workflow_to_s3(self):
        bucket = self.cfg['log_bucket']
        key_prefix = self.jobid + '.workflow/'
        language = self.args.get('language', '')
        if language == 'wdl':
            main_wf = self.args['wdl_main_filename']
            wf_files = self.args.get('wdl_child_filenames', [])
            localdir = self.args['wdl_directory_local']
        elif language == 'snakemake':
            main_wf = self.args['snakemake_main_filename']
            wf_files = self.args.get('snakemake_child_filenames', [])
            localdir = self.args['snakemake_directory_local']
        else:
            main_wf = self.args['cwl_main_filename']
            wf_files = self.args.get('cwl_child_filenames', [])
            localdir = self.args['cwl_directory_local']
        wf_files.append(main_wf)
        localdir = localdir.rstrip('/')
        for wf_file in wf_files:
            source = localdir + '/' + wf_file
            target = key_prefix + wf_file
            boto3.client('s3').upload_file(source, bucket, target)
        return "s3://%s/%s" % (bucket, key_prefix)


def get_file_size(key, bucket, size_in_gb=False):
    '''
    default returns file size in bytes,
    unless size_in_gb = True
    '''
    meta = does_key_exist(bucket, key)
    if not meta:
        raise Exception("key not found: Can't get input file size : %s" % key)
    one_gb = 1073741824
    size = meta['ContentLength']
    if size_in_gb:
        size = size / one_gb
    return size
