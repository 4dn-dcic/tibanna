#!/usr/bin/python
import json
import time
import os
import logging
import boto3
import copy
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
    MissingFieldInInputJsonException,
    EC2LaunchException,
    EC2InstanceLimitException,
    EC2InstanceLimitWaitException,
    DependencyStillRunningException,
    DependencyFailedException
)
from .nnested_array import flatten, run_on_nested_arrays1
from Benchmark import run as B
from Benchmark.classes import get_instance_types, instance_list
logger = logging.getLogger()
logger.setLevel(logging.INFO)
NONSPOT_EC2_PARAM_LIST = ['TagSpecifications', 'InstanceInitiatedShutdownBehavior',
                          'MaxCount', 'MinCount', 'DisableApiTermination']


class UnicornInput(object):
    def __init__(self, input_dict):
        if 'jobid' in input_dict and input_dict.get('jobid'):
            self.jobid = input_dict.get('jobid')
        else:
            self.jobid = create_jobid()
        self.args = Args(**input_dict['args'])  # args is a required field
        self.cfg = Config(**input_dict['config'])  # config is a required field
        # add other fields too
        for field in input_dict:
            if field not in ['jobid', 'args', 'config']:
                setattr(self, field)
        # fill the default values and internally used fields
        self.auto_fill()

    def as_dict(self):
        d = copy.deepcopy(self.__dict__)
        d['args'] = self.args.as_dict()
        d['config'] = self.cfg.as_dict()
        return d

    def auto_fill(self):
        """This function can be called right after initiation (construction)
        of args and cfg objects
        """
        args = self.args
        cfg = self.cfg
        args.fill_default()
        cfg.fill_default()
        cfg.fill_internal()
        cfg.fill_language_options(args.language, getattr(args, 'singularity', False))
        cfg.fill_other_fields(args.app_name)
        # sanity check
        if args.app_name and args.app_name in B.app_name_function_map:
            pass  # use benchmarking
        else:
            if not cfg.ebs_size:  # unset (set to 0)
                cfg.ebs_size = 10  # if not set by user or benchmark, just use 10GB as default
            if not cfg.EBS_optimized:  # either false or unset
                cfg.EBS_optimized = False  # False by default so t2 instances can be used
            if cfg.mem and cfg.cpu:
                pass
            elif cfg.instance_type:
                pass
            else:
                err_msg = "Not enough fields: app_name must be provided in args to use Benchmarking. " + \
                          "Without app_name (or app_name with no benchmarking function defined for it)," + \
                          "either mem and cpu or instance_type must be" + \
                          "in the config field of the execution json, " + \
                          "preferably along with ebs_size (default 10(GB)) and EBS_optimized (default False)."
                raise MissingFieldInInputJsonException(err_msg)
        # add dependency
        dependency = {}
        if hasattr(self, 'dependency') and self.dependency:
            dependency = self.dependency
        elif hasattr(args, 'dependency') and args.dependency:
            dependency = args.dependency
        elif hasattr(cfg, 'dependency') and cfg.dependency:
            dependency = cfg.dependency
        if dependency:
            self.dependency = args.dependency = cfg.dependency = copy.deepcopy(dependency)


class Args(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        for field in ['output_S3_bucket']:
            if not hasattr(self, field):
                raise MissingFieldInInputJsonException("field %s is required in args" % field)
            

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def fill_default(self):
        for field in ['input_files', 'input_parameters', 'input_env',
                      'secondary_files', 'output_target',
                      'secondary_output_target', 'alt_cond_output_argnames']:
            if not hasattr(self, field):
                setattr(self, field, {})
        for field in ['app_version']:
            if not hasattr(self, field):
                setattr(self, field, '')
        # if language and cwl_version is not specified,
        # by default it is cwl_draft3
        if not hasattr(self, 'language'):
            if not hasattr(self, 'cwl_version'):
                self.cwl_version = 'draft3'
                self.language = 'cwl_draft3'
            elif self.cwl_version == 'v1':
                self.language = 'cwl_v1'
            elif self.cwl_version == 'draft3':
                self.language = 'cwl_draft3'
            if not hasattr(self, 'singularity'):
                self.singularity = False
        if not hasattr(self, 'app_name'):
            self.app_name = ''
        # check workflow info is there and fill in default
        errmsg_template = "field %s is required in args for language %s"
        if self.language == 'wdl':
            if not hasattr(self, 'wdl_main_filename'):
                raise MissingFieldInInputJsonException(errmsg_template % ('wdl_main_filename', self.language))
            if not hasattr(self, 'wdl_child_filenames'):
                self.wdl_child_filenames = []
            if not hasattr(self, 'wdl_directory_local'):
                self.wdl_directory_local = ''
            if not hasattr(self, 'wdl_directory_url'):
                self.wdl_directory_url = ''
            if not self.wdl_directory_local and not self.wdl_directory_url:
                errmsg = "either %s or %s must be provided in args" % ('wdl_directory_url', 'wdl_directory_local')
                raise MissingFieldInInputJsonException(errmsg)
        elif self.language == 'snakemake':
            if not hasattr(self, 'snakemake_main_filename'):
                raise MissingFieldInInputJsonException(errmsg_template % ('snakemake_main_filename', self.language))
            if not hasattr(self, 'snakemake_child_filenames'):
                self.snakemake_child_filenames = []
            if not hasattr(self, 'snakemake_directory_local'):
                self.snakemake_directory_local = ''
            if not hasattr(self, 'snakemake_directory_url'):
                self.snakemake_directory_url = ''
            if not self.snakemake_directory_local and not self.snakemake_directory_url:
                errmsg = "either %s or %s must be provided in args" % ('snakemake_directory_url',
                                                                       'snakemake_directory_local')
                raise MissingFieldInInputJsonException(errmsg)
            for field in ['container_image', 'command']:
                if not hasattr(self, field):
                    raise MissingFieldInInputJsonException(errmsg_template % (field, self.language))
        elif self.language == 'shell':
            for field in ['container_image', 'command']:
                if not hasattr(self, field):
                    raise MissingFieldInInputJsonException(errmsg_template % (field, self.language))
        else:
            if not hasattr(self, 'cwl_main_filename'):
                raise MissingFieldInInputJsonException(errmsg_template % ('cwl_main_filename', self.language))
            if not hasattr(self, 'cwl_child_filenames'):
                self.cwl_child_filenames = []
            if not hasattr(self, 'cwl_directory_local'):
                self.cwl_directory_local = ''
            if not hasattr(self, 'cwl_directory_url'):
                self.cwl_directory_url = ''
            if not self.cwl_directory_local and not self.cwl_directory_url:
                errmsg = "either %s or %s must be provided in args" % ('cwl_directory_url', 'cwl_directory_local')
                raise MissingFieldInInputJsonException(errmsg)

    def as_dict(self):
        return self.__dict__


class Config(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        for field in ['log_bucket']:
            if not hasattr(self, field):
                raise MissingFieldInInputJsonException("field %s is required in config" % field)

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def fill_default(self):
        # fill in default
        if not hasattr(self, "instance_type"):
            self.instance_type = ''  # unspecified by default
        if not hasattr(self, "EBS_optimized"):
            self.EBS_optimized = ''  # unspecified by default
        if not hasattr(self, "mem"):
            self.mem = 0  # unspecified by default
        if not hasattr(self, "cpu"):
            self.cpu = ''  # unspecified by default
        if not hasattr(self, "ebs_size"):
            self.ebs_size = 0  # unspecified by default
        if not hasattr(self, "ebs_type"):
            self.ebs_type = 'gp2'
        if not hasattr(self, "ebs_iops"):
            self.ebs_iops = ''
        if not hasattr(self, "shutdown_min"):
            self.shutdown_min = 'now'
        if not hasattr(self, 'password'):
            self.password = ''
        if not hasattr(self, 'key_name'):
            self.key_name = ''
        # postrun json should be made public?
        if not hasattr(self, 'public_postrun_json'):
            self.public_postrun_json = False
            # 4dn will use 'true' --> this will automatically be added by start_run_awsem

    def fill_internal(self):
        # fill internally-used fields (users cannot specify these fields)
        # script url
        self.script_url = 'https://raw.githubusercontent.com/' + \
            TIBANNA_REPO_NAME + '/' + TIBANNA_REPO_BRANCH + '/awsf/'
        self.json_bucket = self.log_bucket

    def fill_language_options(self, language='cwl_draft3', singularity=False):
        """fill in ami_id and language fields (these are also internal)"""
        if language == 'wdl':
            self.ami_id = AMI_ID_WDL
        elif language == 'shell':
            self.ami_id = AMI_ID_SHELL
        elif language == 'snakemake':
            self.ami_id = AMI_ID_SNAKEMAKE
        else:  # cwl
            if language in ['cwl', 'cwl_v1']:  # 'cwl' means 'cwl_v1'
                self.ami_id = AMI_ID_CWL_V1
            else:
                self.ami_id = AMI_ID_CWL_DRAFT3
            if singularity:  # applied to only cwl though it is pretty useless
                self.singularity = True
        self.language = language

    def fill_other_fields(self, app_name=''):
        self.job_tag = app_name

    def as_dict(self):
        return self.__dict__


class Execution(object):

    def __init__(self, input_dict):
        self.unicorn_input = UnicornInput(input_dict)
        self.jobid = self.unicorn_input.jobid
        self.args = self.unicorn_input.args
        self.cfg = self.unicorn_input.cfg
        # store user-specified values for instance type, EBS_optimized and ebs_size
        # separately, since the values in cfg will change.
        self.user_specified_instance_type = self.cfg.instance_type
        self.user_specified_EBS_optimized = self.cfg.EBS_optimized
        self.user_specified_ebs_size = self.cfg.ebs_size
        # get benchmark if available
        self.benchmark = self.get_benchmarking()
        self.init_instance_type_list()
        self.update_config_instance_type()

    @property
    def input_dict(self):
        return self.unicorn_input.as_dict()

    def prelaunch(self, profile=None):
        self.check_dependency(**self.dependency)
        runjson = self.create_run_json_dict()
        self.upload_run_json(runjson)
        self.userdata = self.create_userdata(profile=profile)

    def launch(self):
        self.instance_id = self.launch_and_get_instance_id()
        self.cfg.update(self.get_instance_info())

    def postlaunch(self):
        if self.cfg.cloudwatch_dashboard:
            self.create_cloudwatch_dashboard('awsem-' + self.jobid)

    def init_instance_type_list(self):
        instance_type = self.user_specified_instance_type
        instance_type_dlist = []
        # user directly specified instance type
        if instance_type:
            instance_type_dlist.append(instance_type)
        # user specified mem and cpu
        if self.cfg.mem and self.cfg.cpu:
            list0 = get_instance_types(self.cfg.mem, self.cfg.cpu, instance_list(exclude_t=False))
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
        self.current_instance_type_index = 0  # choose the first one initially

    @property
    def current_instance_type(self):
        if len(self.instance_type_list) > self.current_instance_type_index:
            return self.instance_type_list[self.current_instance_type_index]
        else:
            return ''

    @property
    def current_EBS_optimized(self):
        if self.current_instance_type:
            return self.instance_type_info[self.current_instance_type]['EBS_optimized']
        else:
            return ''

    def choose_next_instance_type(self):
        self.current_instance_type_index += 1
        if len(self.instance_type_list) <= self.current_instance_type_index:
            raise Exception("No more instance type available that matches the criteria")

    def update_config_instance_type(self):
        # deal with missing fields
        self.cfg.instance_type = self.current_instance_type
        if not self.user_specified_EBS_optimized:
            self.cfg.EBS_optimized = self.current_EBS_optimized

    def get_benchmarking(self):
        """add instance_type, ebs_size, EBS_optimized info based on benchmarking.
        user-specified values overwrite the benchmarking.
        """
        input_size_in_bytes = dict()
        for argname, f in iter(self.args.input_files.items()):
            bucket = f['bucket_name']
            if isinstance(f['object_key'], list):
                size = flatten(run_on_nested_arrays1(f['object_key'],
                                                     get_file_size,
                                                     **{'bucket': bucket}))
            else:
                size = get_file_size(f['object_key'], bucket)
            input_size_in_bytes.update({str(argname): size})
        print({"input_size_in_bytes": input_size_in_bytes})
        try:
            res = B.benchmark(self.args.app_name, {'input_size_in_bytes': input_size_in_bytes,
                                                   'parameters': self.args.input_parameters})
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
            return {'instance_type': instance_type, 'EBS_optimized': ebs_opt, 'ebs_size': ebs_size}
        else:
            return {'instance_type': '', 'EBS_optimized': '', 'ebs_size': 0}

    def get_start_time(self):
        return time.strftime("%Y%m%d-%H:%M:%S-%Z")

    def launch_and_get_instance_id(self):
        try:  # capturing stdout from the launch command
            os.environ['AWS_DEFAULT_REGION'] = AWS_REGION
            ec2 = boto3.client('ec2')
        except Exception as e:
            raise Exception("Failed to create a client for EC2")
        while(True):
            try:
                res = 0
                res = ec2.run_instances(**self.launch_args)
                break
            except Exception as e:
                if 'InsufficientInstanceCapacity' in str(e) or 'InstanceLimitExceeded' in str(e):
                    behavior = self.cfg.behavior_on_capacity_limit
                    if behavior == 'fail':
                        errmsg = "Instance limit exception - use 'behavior_on_capacity_limit' option"
                        errmsg += "to change the behavior to wait_and_retry, or retry_without_spot. %s" % str(e)
                        raise EC2InstanceLimitException(errmsg)
                    elif behavior == 'wait_and_retry':
                        errmsg = "Instance limit exception - wait and retry later: %s" % str(e)
                        raise EC2InstanceLimitWaitException(errmsg)
                    elif behavior == 'other_instance_types':
                        try:
                            self.choose_next_instance_type()
                        except Exception as e2:
                            raise EC2InstanceLimitException(str(e2))
                        self.update_config_instance_type()
                        continue
                    elif behavior == 'retry_without_spot':
                        if not self.cfg.spot_instance:
                            errmsg = "'behavior_on_capacity_limit': 'retry_without_spot' works only with"
                            errmsg += "'spot_instance' : true. %s" % str(e)
                            raise Exception(errmsg)
                        try:
                            self.cfg.spot_instance = False
                            printlog("trying without spot : %s" % str(res))
                            continue
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

    def create_run_json_dict(self):
        args = self.args
        cfg = self.cfg
        jobid = self.jobid
        # start time
        start_time = self.get_start_time()
        # pre is a dictionary to be printed as a pre-run json file.
        pre = {'config': cfg.as_dict()}  # copy only config since arg is redundant with 'Job'
        app = {
            'App_name': args.app_name,
            'App_version': args.app_version,
            'language': args.language
        }
        if args.language == 'wdl':
            app.update({
                'main_wdl': args.wdl_main_filename,
                'other_wdl_files': ','.join(args.wdl_child_filenames),
                'wdl_url': args.wdl_directory_url,
            })
        elif args.language == 'snakemake':
            app.update({
                'main_snakemake': args.snakemake_main_filename,
                'other_snakemake_files': ','.join(args.snakemake_child_filenames),
                'snakemake_url': args.snakemake_directory_url,
                'command': args.command,
                'container_image': args.container_image
            })
        elif args.language == 'shell':
            app.update({
                'command': args.command,
                'container_image': args.container_image
            })
        else:
            app.update({
                'main_cwl': args.cwl_main_filename,
                'other_cwl_files': ','.join(args.cwl_child_filenames),
                'cwl_url': args.cwl_directory_url,
            })
        pre.update({'Job': {'JOBID': jobid,
                            'App': app,
                            'Input': {
                                     'Input_files_data': {},    # fill in later (below)
                                     'Secondary_files_data': {},   # fill in later (below)
                                     'Input_parameters': args.input_parameters,
                                     'Env': args.input_env
                            },
                            'Output': {
                                     'output_bucket_directory': args.output_S3_bucket,
                                     'output_target': args.output_target,
                                     'alt_cond_output_argnames': args.alt_cond_output_argnames,
                                     'secondary_output_target': args.secondary_output_target
                            },
                            'Log': {
                                     'log_bucket_directory': cfg.log_bucket
                            },
                            "start_time": start_time
                            }})
        # fill in input_files (restructured)
        for item, value in iter(args.input_files.items()):
            pre['Job']['Input']['Input_files_data'][item] = {'class': 'File',
                                                             'dir': value.get('bucket_name'),
                                                             'path': value.get('object_key'),
                                                             'rename': value.get('rename'),
                                                             'profile': value.get('profile', '')}
        for item, value in iter(args.secondary_files.items()):
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

    def upload_run_json(self, runjson):
        jsonbody = json.dumps(runjson, indent=4, sort_keys=True)
        jsonkey = self.jobid + '.run.json'
        # Keep log of the final json
        logger.info("jsonbody=\n" + jsonbody)
        # copy the json file to the s3 bucket
        logger.info("json_bucket = " + self.cfg.json_bucket)
        try:
            s3 = boto3.client('s3')
        except Exception as e:
            raise Exception("boto3 client error: Failed to connect to s3 : %s" % str(e))
        try:
            res = s3.put_object(Body=jsonbody.encode('utf-8'), Bucket=self.cfg.json_bucket, Key=jsonkey)
        except Exception:
            raise Exception("boto3 client error: Failed to upload run.json %s to s3: %s" % (jsonkey, str(res)))

    def create_userdata(self, profile=None):
        """Create a userdata script to pass to the instance. The userdata script is run_workflow.$JOBID.sh.
        profile is a dictionary { access_key: , secret_key: }
        """
        cfg = self.cfg
        str = ''
        str += "#!/bin/bash\n"
        str += "JOBID={}\n".format(self.jobid)
        str += "RUN_SCRIPT=aws_run_workflow_generic.sh\n"
        str += "SHUTDOWN_MIN={}\n".format(cfg.shutdown_min)
        str += "JSON_BUCKET_NAME={}\n".format(cfg.json_bucket)
        str += "LOGBUCKET={}\n".format(cfg.log_bucket)
        str += "SCRIPT_URL={}\n".format(cfg.script_url)
        str += "LANGUAGE={}\n".format(cfg.language)
        str += "wget $SCRIPT_URL/$RUN_SCRIPT\n"
        str += "chmod +x $RUN_SCRIPT\n"
        str += "source $RUN_SCRIPT -i $JOBID -m $SHUTDOWN_MIN"
        str += " -j $JSON_BUCKET_NAME -l $LOGBUCKET -u $SCRIPT_URL -L $LANGUAGE"
        if cfg.password:
            str += " -p {}".format(cfg.password)
        if profile:
            str += " -a {access_key} -s {secret_key} -r {region}".format(region=AWS_REGION, **profile)
        if hasattr(cfg, 'singularity') and cfg.singularity:
            str += " -g"
        str += "\n"
        print(str)
        return(str)

    @property
    def launch_args(self):
        # creating a launch command
        largs = {'ImageId': self.cfg.ami_id,
                 'InstanceType': self.cfg.instance_type,
                 'IamInstanceProfile': {'Arn': S3_ACCESS_ARN},
                 'UserData': self.userdata,
                 'MaxCount': 1,
                 'MinCount': 1,
                 'InstanceInitiatedShutdownBehavior': 'terminate',
                 'DisableApiTermination': False,
                 'TagSpecifications': [{'ResourceType': 'instance',
                                        "Tags": [{"Key": "Name", "Value": "awsem-" + self.jobid},
                                                 {"Key": "Type", "Value": "awsem"}]}]
                 }
        if self.cfg.key_name:
            largs.update({'KeyName': self.cfg.key_name})
        # EBS options
        if self.cfg.EBS_optimized is True:
            largs.update({"EbsOptimized": True})
        largs.update({"BlockDeviceMappings": [{'DeviceName': '/dev/sdb',
                                               'Ebs': {'DeleteOnTermination': True,
                                                       'VolumeSize': self.cfg.ebs_size,
                                                       'VolumeType': self.cfg.ebs_type}},
                                              {'DeviceName': '/dev/sda1',
                                               'Ebs': {'DeleteOnTermination': True,
                                                       'VolumeSize': 8,
                                                       'VolumeType': 'gp2'}}]})
        if self.cfg.ebs_iops:    # io1 type, specify iops
            largs["BlockDeviceMappings"][0]["Ebs"]['Iops'] = self.cfg.ebs_iops
        if self.cfg.ebs_size >= 16000:
            message = "EBS size limit (16TB) exceeded: (attempted size: %s)" % self.cfg.ebs_size
            raise EC2LaunchException(message)
        if self.cfg.spot_instance:
            spot_options = {'SpotInstanceType': 'one-time',
                            'InstanceInterruptionBehavior': 'terminate'}
            if self.cfg.spot_duration:
                spot_options['BlockDurationMinutes'] = self.cfg.spot_duration
            largs.update({'InstanceMarketOptions': {'MarketType': 'spot',
                                                    'SpotOptions': spot_options}})
        return largs

    def get_instance_info(self):
        # get public IP for the instance (This may not happen immediately)
        try:
            ec2 = boto3.client('ec2')
        except Exception as e:
            raise Exception("Can't create an ec2 client %s" % str(e))
        while(True):  # keep trying until you get the result.
            time.sleep(1)  # wait for one second before trying again.
            try:
                # sometimes you don't get a description immediately
                instance_desc_log = ec2.describe_instances(InstanceIds=[self.instance_id])
                instance_ip = instance_desc_log['Reservations'][0]['Instances'][0]['PublicIpAddress']
                break
            except:
                continue
        return({'instance_id': self.instance_id, 'instance_ip': instance_ip, 'start_time': self.get_start_time()})

    def check_dependency(self, exec_arn=None):
        if exec_arn:
            client = boto3.client('stepfunctions', region_name=AWS_REGION)
            for arn in exec_arn:
                res = client.describe_execution(executionArn=arn)
                if res['status'] == 'RUNNING':
                    raise DependencyStillRunningException("Dependency is still running: %s" % arn)
                elif res['status'] == 'FAILED':
                    raise DependencyFailedException("A Job that this job is dependent on failed: %s" % arn)

    def create_cloudwatch_dashboard(self, dashboard_name):
        instance_id = self.instance_id
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


def upload_workflow_to_s3(unicorn_input):
    """input is a UnicornInput object"""
    args = unicorn_input.args
    cfg = unicorn_input.cfg
    jobid = unicorn_input.jobid
    bucket = cfg.log_bucket
    key_prefix = jobid + '.workflow/'
    if args.language == 'wdl':
        main_wf = args.wdl_main_filename
        wf_files = args.wdl_child_filenames
        localdir = args.wdl_directory_local
    elif args.language == 'snakemake':
        main_wf = args.snakemake_main_filename
        wf_files = args.snakemake_child_filenames
        localdir = args.snakemake_directory_local
    elif args.language == 'shell':
        pass
    else:
        main_wf = args.cwl_main_filename
        wf_files = args.cwl_child_filenames
        localdir = args.cwl_directory_local
    wf_files.append(main_wf)
    localdir = localdir.rstrip('/')
    for wf_file in wf_files:
        source = localdir + '/' + wf_file
        target = key_prefix + wf_file
        boto3.client('s3').upload_file(source, bucket, target)
    url = "s3://%s/%s" % (bucket, key_prefix)
    if args.language == 'wdl':
        args.wdl_directory_url = url
    elif args.language == 'snakemake':
        args.snakemake_directory_url = url
    elif args.language == 'shell':
        pass
    else:
        args.cwl_directory_url = url


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
