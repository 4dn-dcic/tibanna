#!/usr/bin/python
import json
import time
import os
import base64
import logging
import boto3
import botocore
import copy
import re
import random
import string
from . import create_logger
from datetime import datetime, timedelta
from .utils import (
    does_key_exist,
    create_jobid
)
from .vars import (
    AWS_REGION,
    S3_ACCESS_ARN,
    TIBANNA_REPO_NAME,
    TIBANNA_REPO_BRANCH,
    AMI_PER_REGION,
    DYNAMODB_TABLE,
    DEFAULT_ROOT_EBS_SIZE,
    TIBANNA_AWSF_DIR,
    DEFAULT_AWSF_IMAGE,
    S3_ENCRYT_KEY_ID,
)
from .job import Jobs
from .exceptions import (
    MissingFieldInInputJsonException,
    MalFormattedInputJsonException,
    EC2LaunchException,
    EC2InstanceLimitException,
    EC2InstanceLimitWaitException,
    DependencyStillRunningException,
    DependencyFailedException,
    UnsupportedCWLVersionException
)
from .base import SerializableObject
from .nnested_array import flatten, run_on_nested_arrays1
from ._version import __version__
from Benchmark import run as B
from Benchmark.classes import get_instance_types, instance_list
from Benchmark.byteformat import B2GB

NONSPOT_EC2_PARAM_LIST = ['TagSpecifications', 'InstanceInitiatedShutdownBehavior',
                          'MaxCount', 'MinCount', 'DisableApiTermination']


logger = create_logger(__name__)


class UnicornInput(SerializableObject):
    def __init__(self, input_dict, fill_default=True):
        if 'jobid' in input_dict and input_dict.get('jobid'):
            self.jobid = input_dict.get('jobid')
        else:
            self.jobid = create_jobid()
        self.args = Args(**input_dict['args'], fill_default=fill_default)  # args is a required field
        self.cfg = Config(**input_dict['config'], fill_default=fill_default)  # config is a required field
        # add other fields too
        for field, v in input_dict.items():
            if field not in ['jobid', 'args', 'config']:
                setattr(self, field, v)
        if fill_default:
            # fill the default values and internally used fields
            self.auto_fill()

    def as_dict(self):
        d = super().as_dict()
        d['config'] = copy.deepcopy(d['cfg'])
        del(d['cfg'])
        return d

    def auto_fill(self):
        """This function can be called right after initiation (construction)
        of args and cfg objects
        """
        args = self.args
        cfg = self.cfg
        args.fill_default()
        cfg.fill_language_options(args.language, getattr(args, 'singularity', False))
        cfg.fill_other_fields(args.app_name)
        # sanity check
        if args.app_name and args.app_name in B.app_name_function_map:
            pass  # use benchmarking
        else:
            if not cfg.ebs_size:
                cfg.ebs_size = 10  # if not set by user or benchmark, just use 10GB as default
            # This one below may require revisiting - At least in some cases AWS now allows <10GB EBS.
            if isinstance(cfg.ebs_size, int) and cfg.ebs_size < 10:
                cfg.ebs_size = 10  # if user-specified value is less than 10G, use 10GB as default
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
        args.dependency = copy.deepcopy(dependency)


class Args(SerializableObject):
    def __init__(self, fill_default=True, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        for field in ['output_S3_bucket']:
            if not hasattr(self, field):
                raise MissingFieldInInputJsonException("field %s is required in args" % field)
        #if fill_default:
        #    self.fill_default()

    def update(self, d):
        for k, v in d.items():
            setattr(self, k, v)

    def fill_default(self):
        for field in ['input_files', 'input_parameters', 'input_env',
                      'secondary_files', 'output_target',
                      'secondary_output_target', 'alt_cond_output_argnames',
                      'additional_benchmarking_parameters']:
            if not hasattr(self, field):
                setattr(self, field, {})
        for field in ['custom_errors']:
            if not hasattr(self, field):
                setattr(self, field, [])
        for field in ['app_version']:
            if not hasattr(self, field):
                setattr(self, field, '')
        # if language and cwl_version is not specified,
        # by default it is cwl_v1
        if not hasattr(self, 'language'):
            if not hasattr(self, 'cwl_version'):
                self.cwl_version = 'v1'
                self.language = 'cwl_v1'
            elif self.cwl_version == 'v1':
                self.language = 'cwl_v1'
            elif self.cwl_version == 'draft3':
                raise UnsupportedCWLVersionException
            if not hasattr(self, 'singularity'):
                self.singularity = False
        if not hasattr(self, 'app_name'):
            self.app_name = ''
        # input file format check and parsing
        self.parse_input_files()
        # check workflow info is there and fill in default
        errmsg_template = "field %s is required in args for language %s"
        if self.language in ['wdl', 'wdl_v1', 'wdl_draft2']:
            if not hasattr(self, 'wdl_main_filename'):
                raise MissingFieldInInputJsonException(errmsg_template % ('wdl_main_filename', self.language))
            if not hasattr(self, 'wdl_child_filenames'):
                self.wdl_child_filenames = []
            if not hasattr(self, 'wdl_directory_local'):
                self.wdl_directory_local = ''
            if not hasattr(self, 'wdl_directory_url'):
                self.wdl_directory_url = ''
            if not hasattr(self, 'workflow_engine'):
                self.workflow_engine = 'cromwell'
            if not hasattr(self, 'run_args'):
                self.run_args = ''
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
            if not hasattr(self, 'run_args'):
                self.run_args = ''
            if not self.cwl_directory_local and not self.cwl_directory_url:
                errmsg = "either %s or %s must be provided in args" % ('cwl_directory_url', 'cwl_directory_local')
                raise MissingFieldInInputJsonException(errmsg)
        # reformat command
        self.parse_command()

    def parse_command(self):
        """if command is a list, conert it to a string"""
        if hasattr(self, 'command'):
            if isinstance(self.command, list):
                self.command = '; '.join(self.command)
            elif not isinstance(self.command, str):
                raise MalFormattedInputJsonException("command must be either a string or a list")

    def parse_input_files(self):
        """checking format for input files and converting s3:// style string into
        bucket_name and object_key"""
        if hasattr(self, 'input_files'):
            if not isinstance(self.input_files, dict):
                errmsg = "'input_files' must be provided as a dictionary (key-value pairs)"
                raise MalFormattedInputJsonException(errmsg)
            for ip, v in self.input_files.items():
                if isinstance(v, str):
                    bucket_name, object_key = self.parse_s3_url(v)
                    self.input_files[ip] = {'bucket_name': bucket_name, 'object_key': object_key}
                elif isinstance(v, list):
                    buckets = flatten(run_on_nested_arrays1(v, self.parse_s3_url, **{'bucket_only': True}))
                    if len(set(buckets)) != 1:
                        errmsg = "All the input files corresponding to a single input file argument " + \
                                 "must be from the same bucket."
                        raise MalFormattedInputJsonException(errmsg)
                    object_keys = run_on_nested_arrays1(v, self.parse_s3_url, **{'key_only': True})
                    self.input_files[ip] = {'bucket_name': buckets[0], 'object_key': object_keys}
                elif isinstance(v, dict) and 'bucket_name' in v and 'object_key' in v:
                    pass
                else:
                    errmsg = "Each input_file value must be either a string starting with 's3://'" + \
                             " or a dictionary with 'bucket_name' and 'object_key' as keys"
                    raise MalFormattedInputJsonException(errmsg)

    def parse_s3_url(self, url, bucket_only=False, key_only=False):
        if not url.startswith('s3://'):
            raise MalFormattedInputJsonException("S3 url must begin with 's3://'")
        bucket_name = re.sub('^s3://', '', url).split('/')[0]
        object_key = re.sub('^s3://' + bucket_name + '/', '', url)
        if bucket_only:
            return bucket_name
        if key_only:
            return object_key
        return bucket_name, object_key


class Config(SerializableObject):
    def __init__(self, fill_default=True, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        for field in ['log_bucket']:
            if not hasattr(self, field):
                raise MissingFieldInInputJsonException("field %s is required in config" % field)
        if fill_default:
            self.fill_default()
            self.fill_internal()

    def update(self, d):
        for k, v in d.items():
            setattr(self, k, v)

    def fill_default(self):
        # use benchmark or not
        if not hasattr(self, 'use_benchmark'):
            if not hasattr(self, 'instance_type') and (not hasattr(self, 'cpu') or not hasattr(self, 'mem')):
                self.use_benchmark = True
            elif not hasattr(self, 'ebs_size'):
                self.use_benchmark = True
            else:
                self.use_benchmark = False
        # fill in default
        for field in ['instance_type', 'EBS_optimized', 'cpu', 'ebs_iops', 'ebs_throughput', 'password', 'key_name',
                      'spot_duration', 'availability_zone', 'security_group', 'subnet']:
            if not hasattr(self, field):
                setattr(self, field, '')
        if not hasattr(self, "mem"):
            self.mem = 0  # unspecified by default
        if not hasattr(self, "ebs_size"):
            self.ebs_size = 0  # unspecified by default
        if not hasattr(self, "ebs_type"):
            self.ebs_type = 'gp3'
        if not hasattr(self, "shutdown_min"):
            self.shutdown_min = 'now'
        if not hasattr(self, "spot_instance"):
            self.spot_instance = False
        if not hasattr(self, "behavior_on_capacity_limit"):
            self.behavior_on_capacity_limit = 'fail'
        self.cloudwatch_dashboard = False  # now this is always false
        # postrun json should be made public?
        if not hasattr(self, 'public_postrun_json'):
            self.public_postrun_json = False
            # 4dn will use 'true' --> this will automatically be added by start_run_awsem

        # TODO: default to env variable here?
        if not hasattr(self, 'encrypt_s3_upload'):
            self.encrypt_s3_upload = False
        if not hasattr(self, 'kms_key_id'):
            if S3_ENCRYT_KEY_ID:
                self.kms_key_id = S3_ENCRYT_KEY_ID
                self.encrypt_s3_upload = True
            else:
                self.kms_key_id = None
        if not hasattr(self, 'root_ebs_size'):
            self.root_ebs_size = DEFAULT_ROOT_EBS_SIZE
        if not hasattr(self, 'awsf_image'):
            self.awsf_image = DEFAULT_AWSF_IMAGE
        if not hasattr(self, 'mem_as_is'):  # if false, add 1GB overhead
            self.mem_as_is = False
        if not hasattr(self, 'ebs_size_as_is'):  # if false, add 5GB overhead
            self.ebs_size_as_is = False
        if not hasattr(self, 'ami_id'):
            self.ami_id = "" # will be assigned instance architecture specific later
        if not hasattr(self, 'ami_per_region'):
            self.ami_per_region = AMI_PER_REGION
            
        # special handling for subnet, SG if not set already pull from env
        # values from config take priority - omit them to get these values from lambda
        if not self.subnet and os.environ.get('SUBNETS', ''):
            possible_subnets = os.environ['SUBNETS'].split(',')
            self.subnet = possible_subnets  # propagate all subnets here
        if not self.security_group and os.environ.get('SECURITY_GROUPS', ''):
            self.security_group = os.environ['SECURITY_GROUPS'].split(',')[0]

    def fill_internal(self):
        # fill internally-used fields (users cannot specify these fields)
        # script url
        self.script_url = 'https://raw.githubusercontent.com/' + \
            TIBANNA_REPO_NAME + '/' + TIBANNA_REPO_BRANCH + '/' + TIBANNA_AWSF_DIR + '/'
        self.json_bucket = self.log_bucket

    def fill_language_options(self, language='cwl_v1', singularity=False):
        """fill in language fields (these are also internal)"""
        if singularity:
            self.singularity = True
        self.language = language

    def fill_other_fields(self, app_name=''):
        self.job_tag = app_name


class Execution(object):

    def __init__(self, input_dict, dryrun=False):
        self.dryrun = dryrun  # for testing purpose
        self.unicorn_input = UnicornInput(input_dict)
        self.jobid = self.unicorn_input.jobid
        self.args = self.unicorn_input.args
        self.cfg = self.unicorn_input.cfg

        # get benchmark if available
        self.input_size_in_bytes = self.get_input_size_in_bytes()
        if self.cfg.use_benchmark:
            self.benchmark = self.get_benchmarking(self.input_size_in_bytes)
            logger.debug('self.benchmark = ' + str(self.benchmark))
        else:
            logger.debug('self.cfg.use_benchmark = ' + str(self.cfg.use_benchmark))
        logger.debug('self.cfg.as_dict() = ' + str(self.cfg.as_dict()))
        self.create_instance_type_list()
        self.update_config_ebs_size()

    @property
    def input_dict(self):
        return self.unicorn_input.as_dict()

    def prelaunch(self, profile=None):
        self.check_dependency(**self.args.dependency)
        runjson = self.create_run_json_dict()
        self.upload_run_json(runjson)
        self.userdata = self.create_userdata(profile=profile)

    def launch(self):
        self.instance_id = self.launch_and_get_instance_id()
        self.cfg.update(self.get_instance_info())
        self.add_instance_id_to_dynamodb()

    def postlaunch(self):
        if self.cfg.cloudwatch_dashboard:
            self.create_cloudwatch_dashboard('awsem-' + self.jobid)

    def create_instance_type_list(self):
        instance_type = self.cfg.instance_type
        instance_type_dlist = []
        # user directly specified instance type
        if instance_type:
            if isinstance(instance_type, str):
                # Note that the EBS_optimized flag is set on the launch template level
                instance_type_dlist.append({'instance_type': instance_type,
                                            'EBS_optimized': self.cfg.EBS_optimized})
            elif isinstance(instance_type, list):
                for potential_type in instance_type:
                    instance_type_dlist.append({'instance_type': potential_type,
                                                'EBS_optimized': self.cfg.EBS_optimized})

        # user specified mem and cpu - use the benchmark package to retrieve instance types
        if self.cfg.mem and self.cfg.cpu:
            mem = self.cfg.mem if self.cfg.mem_as_is else self.cfg.mem + 1
            list0 = get_instance_types(self.cfg.cpu, mem, instance_list(exclude_t=False))
            current_list = [i['instance_type'] for i in instance_type_dlist]
            nonredundant_list = [i for i in list0 if i['instance_type'] not in current_list]
            instance_type_dlist.extend(nonredundant_list)

        # add benchmark only if there is no user specification
        if len(instance_type_dlist) == 0 and self.benchmark['instance_type']:
            instance_type_dlist.append(self.benchmark)

        # Augment the list with the corresponding AMI ID and EBS_optimized flag
        ec2 = boto3.client('ec2')
        current_instance_types = [i['instance_type'] for i in instance_type_dlist]
        ami_ebs_info = {}
        results = ec2.describe_instance_types(
            InstanceTypes=current_instance_types
        )
        for result in results['InstanceTypes']:
            instance_type = result['InstanceType']
            is_ebs_optimized = result['EbsInfo']['EbsOptimizedSupport'] != 'unsupported'
            ami_ebs_info[instance_type] = {
                'EBS_optimized': is_ebs_optimized
            }
            arch = result['ProcessorInfo']['SupportedArchitectures'][0]
            default_ami = self.cfg.ami_per_region['Arm'].get(AWS_REGION, '') if arch == 'arm64' else self.cfg.ami_per_region['x86'].get(AWS_REGION, '')
            if self.cfg.ami_id:
                # if a user supplied an ami_id, it will be used for every instance. 
                # will be problematic if the instance list contains x86 and Arm instances
                # Instead, users should provide ami_per_region
                ami_ebs_info[instance_type]['ami_id'] = self.cfg.ami_id
            elif default_ami:
                ami_ebs_info[instance_type]['ami_id'] = default_ami
            else:
                raise Exception(f"No AMI found for {result['InstanceType']} ({arch}) in {AWS_REGION}")
        for instance in instance_type_dlist:
            it = instance['instance_type']
            instance['ami_id'] = ami_ebs_info[it]['ami_id']
            instance['EBS_optimized'] = ami_ebs_info[it]['EBS_optimized']

        # Filtering: user specifically wanted EBS_optimized instances
        if self.cfg.EBS_optimized:
            instance_type_dlist = [i for i in instance_type_dlist if i['EBS_optimized']]

        if len(instance_type_dlist) == 0:
            raise Exception("There are no EC2 instances that match the provided configuration.")
        
        self.instance_type_list = [i['instance_type'] for i in instance_type_dlist]
        self.instance_type_infos = {i['instance_type']: i for i in instance_type_dlist}

    @property
    def total_input_size_in_gb(self):
        if not hasattr(self, 'input_size_in_bytes'):
            raise Exception("Cannot calculate total input size " +
                            "- run get_input_size_in_bytes() first")
        try:
            return B2GB(sum([sum(flatten([v])) for s, v in self.input_size_in_bytes.items()]))
        except:
            return None

    def update_config_ebs_size(self):
        """if ebs_size is in the format of e.g. '3x', it updates the size
        to be total input size times three. If the value is lower than 10GB,
        keep 10GB"""
        if isinstance(self.cfg.ebs_size, str) and self.cfg.ebs_size.endswith('x'):
            multiplier = float(self.cfg.ebs_size.rstrip('x'))
            if not self.total_input_size_in_gb:
                raise Exception("Cannot calculate ebs size - input size unavailable," +
                                "possibly because the lambda does not have permission to input files." +
                                "Specify the actual GB when input file size is unavailable")
            self.cfg.ebs_size = multiplier * self.total_input_size_in_gb
            if round(self.cfg.ebs_size) < self.cfg.ebs_size:
                self.cfg.ebs_size = round(self.cfg.ebs_size) + 1
            else:
                self.cfg.ebs_size = round(self.cfg.ebs_size)
        if not self.cfg.ebs_size:  # use benchmark only if not set by user
            self.cfg.ebs_size = self.benchmark['ebs_size']
        if not self.cfg.ebs_size_as_is:
            self.cfg.ebs_size += 5  # account for docker image size
        if self.cfg.ebs_size < 10:
            self.cfg.ebs_size = 10

    def get_input_size_in_bytes(self):
        input_size_in_bytes = dict()
        input_plus_secondary_files = copy.deepcopy(self.args.input_files)
        if self.args.secondary_files:
            secondary_files_as_input = {k+'_secondary': v for k, v in self.args.secondary_files.items()
                                        if is_not_empty(v['object_key'])}
            input_plus_secondary_files.update(secondary_files_as_input)
        for argname, f in iter(input_plus_secondary_files.items()):
            bucket = f['bucket_name']
            if isinstance(f['object_key'], list):
                size = flatten(run_on_nested_arrays1(f['object_key'],
                                                     get_file_size,
                                                     **{'bucket': bucket}))
            else:
                size = get_file_size(f['object_key'], bucket)
            input_size_in_bytes.update({str(argname): size})
        logger.debug(str({"input_size_in_bytes": input_size_in_bytes}))
        return input_size_in_bytes

    def get_benchmarking(self, input_size_in_bytes):
        benchmark_parameters = copy.deepcopy(self.args.input_parameters)
        benchmark_parameters.update(self.args.additional_benchmarking_parameters)
        try:
            res = B.benchmark(self.args.app_name, {'input_size_in_bytes': input_size_in_bytes,
                                                   'parameters': benchmark_parameters})
        except Exception as e:
            try:
                raise Exception("Benchmarking not working. : {}".format(str(res)))
            except:
                raise Exception("Benchmarking not working. : None. %s" % str(e))
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
        os.environ['AWS_DEFAULT_REGION'] = AWS_REGION 
        invalid_launch_template_retries = 0

        self.create_launch_template()

        while True:
            fleet_result = self.create_fleet()
            
            if 'Errors' in fleet_result and len(fleet_result['Errors']) > 0:
                error_code = fleet_result['Errors'][0]['ErrorCode']
                error_msg = fleet_result['Errors'][0]['ErrorMessage']


                if ('InsufficientInstanceCapacity' in error_code or 'InstanceLimitExceeded' in error_code                        
                        or 'UnfulfillableCapacity' in error_code):
                    
                    if 'FleetId' in fleet_result:
                        self.delete_fleet(fleet_result['FleetId'])

                    behavior = self.cfg.behavior_on_capacity_limit
                    if behavior == 'fail':
                        self.delete_launch_template()
                        msg = "Instance limit exception - use 'behavior_on_capacity_limit' option " + \
                              "to change the behavior to wait_and_retry, " + \
                              "or retry_without_spot. %s" % error_msg
                        raise EC2InstanceLimitException(msg)
                    elif behavior == 'wait_and_retry' or behavior == 'other_instance_types': # 'other_instance_types' is there for backwards compatibility
                        self.delete_launch_template()
                        msg = "Instance limit exception - wait and retry later: %s" % error_msg
                        raise EC2InstanceLimitWaitException(msg)
                    elif behavior == 'retry_without_spot':
                        if not self.cfg.spot_instance:
                            self.delete_launch_template()
                            msg = "'behavior_on_capacity_limit': 'retry_without_spot' works only with " + \
                                  "'spot_instance' : true. %s" % error_msg
                            raise Exception(msg)
                        else:
                            self.cfg.spot_instance = False
                            # change behavior as well,
                            # to avoid 'retry_without_spot works only with spot' error in the next round
                            self.cfg.behavior_on_capacity_limit = 'fail'
                            logger.info("trying without spot...")
                            continue
                elif 'is not supported in your requested Availability Zone' in error_msg:
                    if 'FleetId' in fleet_result:
                        self.delete_launch_template()
                        instance_id = fleet_result['Instances'][0]['InstanceIds'][0]
                        return instance_id
                    else:
                        self.delete_launch_template()
                        raise Exception(f"Failed to launch instance for job {self.jobid}. {error_code}: {error_msg}")

                elif 'InvalidLaunchTemplate' in error_code and invalid_launch_template_retries < 5:
                    if 'FleetId' in fleet_result:
                        self.delete_fleet(fleet_result['FleetId'])
                    invalid_launch_template_retries += 1
                    logger.info(f"LaunchTemplate not found. Retry #{invalid_launch_template_retries}")
                    continue
                else:
                    self.delete_launch_template()
                    if 'FleetId' in fleet_result:
                        self.delete_fleet(fleet_result['FleetId'])
                    raise Exception(f"Failed to launch instance for job {self.jobid}. {error_code}: {error_msg}")
            elif 'Instances' in fleet_result and len(fleet_result['Instances']) > 0:
                self.delete_launch_template()
                instance_id = fleet_result['Instances'][0]['InstanceIds'][0]
                return instance_id
            else:
                self.delete_launch_template()
                if 'FleetId' in fleet_result:
                    self.delete_fleet(fleet_result['FleetId'])
                raise Exception(f"Unexpected result from create_fleet command: {json.dumps(fleet_result)}")

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
        if args.language in ['wdl', 'wdl_v1', 'wdl_draft2']:
            app.update({
                'main_wdl': args.wdl_main_filename,
                'other_wdl_files': ','.join(args.wdl_child_filenames),
                'wdl_url': args.wdl_directory_url,
                'workflow_engine': args.workflow_engine,
                'run_args': args.run_args
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
                'run_args': args.run_args
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
            if value.get('unzip', '') not in ['gz', 'bz2', '']:
                raise MalFormattedInputJsonException("unzip field must be gz, bz2 or ''")
            pre['Job']['Input']['Input_files_data'][item] = {'class': 'File',
                                                             'dir': value.get('bucket_name'),
                                                             'path': value.get('object_key'),
                                                             'rename': value.get('rename'),
                                                             'profile': value.get('profile', ''),
                                                             'unzip': value.get('unzip', ''),
                                                             'mount': value.get('mount', '')}

        for item, value in iter(args.secondary_files.items()):
            if value.get('unzip', '') not in ['gz', 'bz2', '']:
                raise MalFormattedInputJsonException("unzip field must be gz, bz2 or ''")
            pre['Job']['Input']['Secondary_files_data'][item] = {'class': 'File',
                                                                 'dir': value.get('bucket_name'),
                                                                 'path': value.get('object_key'),
                                                                 'rename': value.get('rename'),
                                                                 'profile': value.get('profile', ''),
                                                                 'unzip': value.get('unzip', ''),
                                                                 'mount': value.get('mount', '')}
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
        upload_args = {
            'Body': jsonbody.encode('utf-8'),
            'Bucket': self.cfg.json_bucket,
            'Key': jsonkey
        }
        if self.cfg.encrypt_s3_upload:
            upload_args.update({'ServerSideEncryption': 'aws:kms'})
            if self.cfg.kms_key_id:
                upload_args['SSEKMSKeyId'] = self.cfg.kms_key_id
        try:
            s3 = boto3.client('s3')
        except Exception as e:
            raise Exception("boto3 client error: Failed to connect to s3 : %s" % str(e))
        try:
            s3.put_object(**upload_args)
        except Exception as e:
            raise Exception("boto3 client error: Failed to upload run.json %s to s3: %s" % (jsonkey, str(e)))

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
        str += "LOGBUCKET={}\n".format(cfg.log_bucket)
        str += "SCRIPT_URL={}\n".format(cfg.script_url)
        str += "wget $SCRIPT_URL/$RUN_SCRIPT\n"
        str += "chmod +x $RUN_SCRIPT\n"
        str += "source $RUN_SCRIPT -i $JOBID -m $SHUTDOWN_MIN"
        str += " -l $LOGBUCKET"
        str += " -V {version}".format(version=__version__)
        str += " -A {awsf_image}".format(awsf_image=cfg.awsf_image)
        if cfg.kms_key_id:
            str += " -k %s" % cfg.kms_key_id
        if cfg.password:
            str += " -p {}".format(cfg.password)
        if profile:
            str += " -a {access_key} -s {secret_key} -r {region}".format(region=AWS_REGION, **profile)
        if hasattr(cfg, 'singularity') and cfg.singularity:
            str += " -g"
        str += "\n"
        logger.debug("userdata: \n" + str)

        # The launch template expects base64 encoded text
        str_bytes = str.encode('ascii')
        base64_bytes = base64.b64encode(str_bytes)
        base64_message = base64_bytes.decode('ascii')
        return base64_message

    def delete_launch_template(self):
        try:
            # Existing launch templates can't be overwritten. Therefore, delete
            # exsting ones first
            ec2 = boto3.client('ec2')
            ec2.delete_launch_template(
                DryRun=self.dryrun,
                LaunchTemplateName=self.launch_template_name,
            )
        except Exception as e:
            logger.info("No existing launch template found.")


    def create_launch_template(self):
        """Create a launch template everytime we run a workflow. There is no other
        way to specify the necessary EC2 configurations"""
        ec2 = boto3.client('ec2')
        lt_id = ''.join(random.choices(string.ascii_lowercase, k=8))
        self.launch_template_name = f'TibannaLaunchTemplate_{lt_id}'

        # ImageId, InstanceType and SubnetId will be set during the create-fleet operation
        launch_template_data ={
            'IamInstanceProfile': {'Arn': S3_ACCESS_ARN},
            'UserData': self.userdata,
            'InstanceInitiatedShutdownBehavior': 'terminate',
            'DisableApiTermination': False,
            'BlockDeviceMappings': [
                {
                    'DeviceName': '/dev/sdb',
                    'Ebs': 
                        {
                            'DeleteOnTermination': True,
                            'VolumeSize': self.cfg.ebs_size,
                            'VolumeType': self.cfg.ebs_type
                        }
                },
                {
                    'DeviceName': '/dev/sda1',
                    'Ebs': 
                        {
                            'DeleteOnTermination': True,
                            'VolumeSize': self.cfg.root_ebs_size,
                            'VolumeType': 'gp3'
                        }
                }
            ],
            'TagSpecifications': [
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {"Key": "Name", "Value": "awsem-" + self.jobid},
                        {"Key": "Type", "Value": "awsem"}
                    ]
                }
            ]
        }

        if self.cfg.key_name:
            launch_template_data.update({'KeyName': self.cfg.key_name})
        if self.cfg.EBS_optimized is True:
            launch_template_data.update({"EbsOptimized": True})
        if self.cfg.ebs_iops:    # io1 type, specify iops
            launch_template_data["BlockDeviceMappings"][0]["Ebs"]['Iops'] = self.cfg.ebs_iops
        if self.cfg.ebs_throughput and self.cfg.ebs_type == 'gp3':
            if self.cfg.ebs_throughput < 125 or self.cfg.ebs_throughput > 1000:
                message = "Invalid EBS throughput. Specify a value between 125 and 1000."
                raise EC2LaunchException(message)
            launch_template_data["BlockDeviceMappings"][0]["Ebs"]['Throughput'] = self.cfg.ebs_throughput
        if self.cfg.ebs_size >= 16000:
            message = "EBS size limit (16TB) exceeded: (attempted size: %s)" % self.cfg.ebs_size
            raise EC2LaunchException(message)

        
        if self.cfg.availability_zone:
            launch_template_data.update({'Placement': {'AvailabilityZone': self.cfg.availability_zone}})
        if self.cfg.security_group:
            launch_template_data.update({'SecurityGroupIds': [self.cfg.security_group]})

        if self.cfg.spot_instance:
            spot_options = {'SpotInstanceType': 'one-time',
                            'InstanceInterruptionBehavior': 'terminate'}
            if self.cfg.spot_duration:
                spot_options['BlockDurationMinutes'] = self.cfg.spot_duration
            launch_template_data.update(
                {'InstanceMarketOptions': 
                    {'MarketType': 'spot','SpotOptions': spot_options}
                }
            )

        try:
            ec2.create_launch_template(
                DryRun=self.dryrun,
                LaunchTemplateName=self.launch_template_name,
                LaunchTemplateData=launch_template_data,
            )
        except Exception as e:
            raise Exception(f"Could not create launch template: {str(e)}")


    def delete_fleet(self, fleet_id):
        '''Delete an existing fleet'''
        ec2 = boto3.client('ec2')
        try:
            return ec2.delete_fleets(
                DryRun=self.dryrun,
                FleetIds=[fleet_id],
                TerminateInstances=True
            )
        except Exception as e:
            raise Exception(f"Unable to delete fleet: {str(e)}")
        

    def create_fleet(self):
        '''Create an 'instant' type fleet with 1 instance'''
        ec2 = boto3.client('ec2')
        try:
            fleet_spec = self.create_fleet_spec()
            fleet_result = ec2.create_fleet(**fleet_spec)
            return fleet_result
        except Exception as e:
            raise Exception(f"Unable to create fleet: {str(e)}")


    def create_fleet_spec(self): # Factored out for easier testing

        potential_ec2s = [] # Used as overrides in the launch template

        subnets = False
        if self.cfg.subnet:
            if isinstance(self.cfg.subnet, str):
                subnets = [self.cfg.subnet]
            elif isinstance(self.cfg.subnet, list):
                subnets = self.cfg.subnet

        # Create all possible combinations of instance type / subnet
        for instance_type in self.instance_type_list:
            instance_info = self.instance_type_infos[instance_type]
            if subnets:
                for subnet in subnets:
                    potential_ec2s.append({
                        "InstanceType": instance_type,
                        "SubnetId": subnet,
                        "ImageId": instance_info['ami_id']
                    })
            else:
                potential_ec2s.append({
                    "InstanceType": instance_type,
                    "ImageId": instance_info['ami_id']
                })
        
        spec = {
            "DryRun": self.dryrun,
            "SpotOptions": {
                "AllocationStrategy": "capacity-optimized",
                "InstanceInterruptionBehavior": "terminate" # hibernate is an option here
            },
            "OnDemandOptions": {
                "AllocationStrategy": "lowest-price" # prioritized is the other option, but then we need to assign prioritoes in the launch template
            },
            "LaunchTemplateConfigs": [{
                "LaunchTemplateSpecification": {
                    "LaunchTemplateName": self.launch_template_name,
                    "Version": "$Latest" # There is only one version
                },
                "Overrides": potential_ec2s,
                
            }],
            "TargetCapacitySpecification": {
                "TotalTargetCapacity": 1,
                "DefaultTargetCapacityType": "spot" if self.cfg.spot_instance else "on-demand",
            },
            "Type": "instant" 
        }

        return spec



    def get_instance_info(self):
        # get public IP and availablity zone for the instance (This may not happen immediately)
        try:
            ec2 = boto3.client('ec2')
        except Exception as e:
            raise Exception("Can't create an ec2 client %s" % str(e))
        while True:  # keep trying until you get the result.
            time.sleep(1)  # wait for one second before trying again.
            try:
                # sometimes you don't get a description immediately
                instance_desc_log = ec2.describe_instances(InstanceIds=[self.instance_id])
                if 'PublicIpAddress' not in instance_desc_log['Reservations'][0]['Instances'][0]:
                    instance_ip = ''
                    availability_zone = ''
                    break
                instance_ip = instance_desc_log['Reservations'][0]['Instances'][0]['PublicIpAddress']
                availability_zone = instance_desc_log['Reservations'][0]['Instances'][0]["Placement"]["AvailabilityZone"]
                break
            except:
                continue
        return({'instance_id': self.instance_id,
                'instance_ip': instance_ip,
                'availability_zone' : availability_zone,
                'start_time': self.get_start_time()})

    @staticmethod
    def check_dependency(exec_arn=None, job_id=None):
        """take a list of exec_arns and/or a list of job_ids
        and raise DependencyFailedException if any of these failed
        or raise DependencyStillRunningException if any of these are running.
        """
        job_statuses = Jobs.status(job_ids=job_id, exec_arns=exec_arn)
        if job_statuses['failed_jobs']:
            raise DependencyFailedException("A Job that this job is dependent on failed: %s" % ','.join(job_statuses['failed_jobs']))
        if job_statuses['running_jobs']:
            raise DependencyStillRunningException("Dependency is still running: %s" % ','.join(job_statuses['running_jobs']))

    def add_instance_id_to_dynamodb(self):
        dd = boto3.client('dynamodb')
        try:
            dd.update_item(
                TableName=DYNAMODB_TABLE,
                Key={
                    'Job Id': {
                        'S': self.jobid
                    }
                },
                AttributeUpdates={
                    'instance_id': {
                        'Value': {
                            'S': self.instance_id
                        },
                        'Action': 'PUT'
                    }
                }
            )
        except:
            pass

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
    if args.language in ['wdl', 'wdl_v1', 'wdl_draft2']:
        main_wf = args.wdl_main_filename
        wf_files = args.wdl_child_filenames.copy()
        localdir = args.wdl_directory_local
    elif args.language == 'snakemake':
        main_wf = args.snakemake_main_filename
        wf_files = args.snakemake_child_filenames.copy()
        localdir = args.snakemake_directory_local
    elif args.language == 'shell':
        pass
    else:
        main_wf = args.cwl_main_filename
        wf_files = args.cwl_child_filenames.copy()
        localdir = args.cwl_directory_local
    wf_files.append(main_wf)
    localdir = localdir.rstrip('/')
    # encrypted s3 upload
    extra_args = {}
    if cfg.encrypt_s3_upload:
        extra_args.update({"ServerSideEncryption": "aws:kms"})
    s3 = boto3.client('s3')
    for wf_file in wf_files:
        source = localdir + '/' + wf_file
        target = key_prefix + wf_file
        s3.upload_file(source, bucket, target, ExtraArgs=extra_args)
    url = "s3://%s/%s" % (bucket, key_prefix)
    if args.language == 'wdl':
        args.wdl_directory_url = url
    elif args.language == 'snakemake':
        args.snakemake_directory_url = url
    elif args.language == 'shell':
        pass
    else:
        args.cwl_directory_url = url


def get_all_objects_in_prefix(bucketname, prefix):
    lastkey = ''
    while True:
        response = boto3.client('s3').list_objects(
            Bucket=bucketname,
            Prefix=prefix,
            Marker=lastkey,
            MaxKeys=1000
        )
        if not response.get('Contents'):
            break
        lastkey = [item['Key'] for item in response['Contents']][-1]
        for item in response['Contents']:
            yield item


def get_file_size(key, bucket, size_in_gb=False):
    '''
    default returns file size in bytes,
    unless size_in_gb = True
    '''
    logger.info("getting file or subfoler size")
    meta = does_key_exist(bucket, key)
    if not meta:
        try:
            size = 0
            logger.info("trying to get total size of the prefix")
            for item in get_all_objects_in_prefix(bucket, key):
                size += item['Size']
        except:
            return None  # do not throw an error here - if lambda doens't have s3 access, pass.
            # s3 bucket access permissions may be quite complex - e.g. some buckets may work only
            # on EC2 instance, which means a lambda would not be able to get the file size.
    else:
        size = meta['ContentLength']
    one_gb = 1073741824
    if size_in_gb:
        size = size / one_gb
    return size


def is_not_empty(x):
    if not isinstance(x, list):
        if x:
            return True
        else:
            return False
    else:
        if list(filter(lambda x: x, flatten(x))):
            return True
        else:
            return False
