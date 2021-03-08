import boto3
import pytest
import os
import json
import mock
from tibanna.job import Jobs
from tibanna.ec2_utils import (
    UnicornInput,
    Args,
    Config,
    Execution,
    upload_workflow_to_s3,
    get_file_size,
    cost_estimate
)
from tibanna.utils import create_jobid
from tibanna.exceptions import (
    MissingFieldInInputJsonException,
    MalFormattedInputJsonException,
    EC2InstanceLimitException,
    EC2InstanceLimitWaitException,
    DependencyStillRunningException,
    DependencyFailedException
)
from tibanna.awsem import AwsemRunJson, AwsemPostRunJson


def fun():
    raise Exception("InstanceLimitExceeded")


def test_args():
    input_dict = {'args': {'input_files': {}, 'output_S3_bucket': 'somebucket', 'app_name': 'someapp'}}
    args = Args(**input_dict['args'], fill_default=False)
    args_dict = args.as_dict()
    assert 'input_files' in args_dict
    assert 'app_name' in args_dict
    assert args_dict['app_name'] == 'someapp'


def test_args_missing_field():
    input_dict = {'args': {'input_files': {}, 'app_name': 'someapp'}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        Args(**input_dict['args'])
    assert ex
    assert 'output_S3_bucket' in str(ex.value)


def test_args_parse_input_files():
    input_dict = {'args': {'input_files': {"file1": "s3://somebucket/somekey"},
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl',
                           'app_name': 'someapp'}}
    args = Args(**input_dict['args'])
    args.fill_default()
    assert hasattr(args, 'input_files')
    assert 'file1' in args.input_files
    assert 'bucket_name' in args.input_files['file1']
    assert 'object_key' in args.input_files['file1']
    assert args.input_files['file1']['bucket_name'] == 'somebucket'
    assert args.input_files['file1']['object_key'] == 'somekey'


def test_args_parse_input_files2():
    input_dict = {'args': {'input_files': {"file1": [["s3://somebucket/somekey1",
                                                      "s3://somebucket/somekey2"],
                                                     ["s3://somebucket/somekey3",
                                                      "s3://somebucket/somekey4"]]},
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl',
                           'app_name': 'someapp'}}
    args = Args(**input_dict['args'])
    args.fill_default()
    assert hasattr(args, 'input_files')
    assert 'file1' in args.input_files
    assert 'bucket_name' in args.input_files['file1']
    assert 'object_key' in args.input_files['file1']
    assert args.input_files['file1']['bucket_name'] == 'somebucket'
    assert isinstance(args.input_files['file1']['object_key'], list)
    assert len(args.input_files['file1']['object_key']) == 2
    assert isinstance(args.input_files['file1']['object_key'][0], list)
    assert len(args.input_files['file1']['object_key'][0]) == 2
    assert isinstance(args.input_files['file1']['object_key'][1], list)
    assert len(args.input_files['file1']['object_key'][1]) == 2
    assert args.input_files['file1']['object_key'][0][0] == 'somekey1'
    assert args.input_files['file1']['object_key'][0][1] == 'somekey2'
    assert args.input_files['file1']['object_key'][1][0] == 'somekey3'
    assert args.input_files['file1']['object_key'][1][1] == 'somekey4'


def test_args_parse_input_files3():
    input_dict = {'args': {'input_files': {"file1": ["s3://somebucket/somekey1",
                                                     "s3://somebucket/somekey2"]},
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl',
                           'app_name': 'someapp'}}
    args = Args(**input_dict['args'])
    args.fill_default()
    assert hasattr(args, 'input_files')
    assert 'file1' in args.input_files
    assert 'bucket_name' in args.input_files['file1']
    assert 'object_key' in args.input_files['file1']
    assert args.input_files['file1']['bucket_name'] == 'somebucket'
    assert isinstance(args.input_files['file1']['object_key'], list)
    assert len(args.input_files['file1']['object_key']) == 2
    assert args.input_files['file1']['object_key'][0] == 'somekey1'
    assert args.input_files['file1']['object_key'][1] == 'somekey2'


def test_args_parse_input_files_format_error():
    input_dict = {'args': {'input_files': {"file1": "somerandomstr"},
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl',
                           'app_name': 'someapp'}}
    args = Args(**input_dict['args'], fill_default=False)
    with pytest.raises(MalFormattedInputJsonException) as ex:
        args.fill_default()
    assert ex
    assert 'S3 url must begin with' in str(ex.value)


def test_args_parse_input_files_format_error2():
    input_dict = {'args': {'input_files': {"file1": ["s3://somebucket/somekey1",
                                                     "s3://otherbucket/somekey2"]},
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl',
                           'app_name': 'someapp'}}
    args = Args(**input_dict['args'], fill_default=False)
    with pytest.raises(MalFormattedInputJsonException) as ex:
        args.fill_default()
    assert ex
    assert 'bucket' in str(ex.value)


def test_args_input_files_w_mount():
    input_dict = {'args': {'input_files': {
                               "file1": {"bucket_name": "a", "object_key": "b", "mount": True}
                           },
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl',
                           'app_name': 'someapp'}}
    args = Args(**input_dict['args'])
    assert args.input_files['file1']['mount']


def test_parse_command():
    input_dict = {'args': {'command': ['command1', 'command2', 'command3'],
                           'output_S3_bucket': 'somebucket',
                           'language': 'shell',
                           'container_image': 'someimage',
                           'app_name': 'someapp'}}
    args = Args(**input_dict['args'])
    args.fill_default()
    assert args.command == 'command1; command2; command3'


def test_config():
    input_dict = {'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    cfg = Config(**input_dict['config'])
    cfg_dict = cfg.as_dict()
    assert 'log_bucket' in cfg_dict
    assert 'shutdown_min' in cfg_dict
    assert cfg_dict['shutdown_min'] == 30


def test_config2():
    input_dict = {'config': {'log_bucket': 'tibanna-output'}}
    cfg = Config(**input_dict['config'])
    cfg.fill_default()
    cfg_dict = cfg.as_dict()
    assert 'log_bucket' in cfg_dict
    assert 'shutdown_min' in cfg_dict
    assert 'root_ebs_size' in cfg_dict
    assert cfg_dict['shutdown_min'] == 'now'
    assert cfg_dict['root_ebs_size'] == 8


def test_config_root_ebs_size():
    input_dict = {'config': {'log_bucket': 'tibanna-output', 'root_ebs_size': 20}}
    cfg = Config(**input_dict['config'])
    cfg.fill_default()
    cfg_dict = cfg.as_dict()
    assert 'log_bucket' in cfg_dict
    assert cfg_dict['root_ebs_size'] == 20


def test_unicorn_input():
    input_dict = {'args': {'input_files': {}, 'app_name': 'bwa-mem',
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    unicorn_input = UnicornInput(input_dict)
    unicorn_dict = unicorn_input.as_dict()
    print(unicorn_dict)
    assert 'args' in unicorn_dict
    assert 'config' in unicorn_dict
    assert 'jobid' in unicorn_dict  # should be created


def test_unicorn_input2():
    """instance_type is provided but not app_name, which should be fine.
    ebs_size is not provided (no benchmarking) so default value (10) is entered
    also testing non-conventional fields
    language is wdl this time"""
    input_dict = {'args': {'input_files': {}, 'language': 'wdl',
                           'output_S3_bucket': 'somebucket',
                           'wdl_main_filename': 'main.wdl',
                           'wdl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'instance_type': 't2.nano'},
                  '_tibanna': {}}
    unicorn_input = UnicornInput(input_dict)
    unicorn_dict = unicorn_input.as_dict()
    print(unicorn_dict)
    assert 'args' in unicorn_dict
    assert 'config' in unicorn_dict
    assert 'ebs_size' in unicorn_dict['config']
    assert unicorn_dict['config']['ebs_size'] == 10


def test_execution_mem_cpu():
    """mem and cpu are provided but not app_name or instance_type,
    which should be fine.
    language is snakemake this time"""
    input_dict = {'args': {'input_files': {}, 'language': 'snakemake',
                           'output_S3_bucket': 'somebucket',
                           'snakemake_main_filename': 'Snakefile',
                           'snakemake_directory_url': 'someurl',
                           'command': 'snakemake',
                           'container_image': 'snakemake/snakemake'},
                  'config': {'log_bucket': 'tibanna-output', 'mem': 1, 'cpu': 1}}
    execution = Execution(input_dict)
    unicorn_dict = execution.input_dict
    assert len(execution.instance_type_list) == 10
    assert 'args' in unicorn_dict
    assert 'config' in unicorn_dict
    assert 'instance_type' in unicorn_dict['config']
    assert unicorn_dict['config']['instance_type'] == 't3.micro'


def test_execution_benchmark():
    randomstr = 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr)
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'tibanna-output',
                                                          'object_key': randomstr}},
                           'output_S3_bucket': 'somebucket',
                           'app_name': 'md5',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output'}}
    execution = Execution(input_dict)
    unicorn_dict = execution.input_dict
    print(unicorn_dict)
    assert 'args' in unicorn_dict
    assert 'config' in unicorn_dict
    assert 'instance_type' in unicorn_dict['config']
    assert unicorn_dict['config']['instance_type'] == 't3.micro'
    assert unicorn_dict['config']['ebs_size'] == 10
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr}]})


def test_get_file_size():
    randomstr = 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr)
    size = get_file_size(randomstr, 'tibanna-output')
    assert size == 4
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr}]})


def test_get_file_size2():
    randomstr = 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr + '/1')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr + '/2')
    size = get_file_size(randomstr, 'tibanna-output')
    assert size == 8
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr + '/1'},
                                          {'Key': randomstr + '/2'}]})


def test_get_input_size_in_bytes():
    randomstr = 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr)
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'tibanna-output',
                                                          'object_key': randomstr}},
                           'output_S3_bucket': 'somebucket',
                           'app_name': 'md5',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output'}}
    execution = Execution(input_dict)
    execution.input_size_in_bytes = execution.get_input_size_in_bytes()
    assert execution.total_input_size_in_gb > 3E-9
    assert execution.total_input_size_in_gb < 4E-9
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr}]})


def test_get_input_size_in_bytes_with_secondary_files():
    randomstr, randomstr_1, randomstr_2 = 'test-' + create_jobid(), 'test-' + create_jobid(), 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr)
    s3.put_object(Body='fooooooo'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr_1)
    s3.put_object(Body='pippo'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr_2)
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'tibanna-output',
                                                          'object_key': randomstr}},
                           'secondary_files': {'input_file': {'bucket_name': 'tibanna-output',
                                                              'object_key': [randomstr_1, randomstr_2]}},
                           'output_S3_bucket': 'somebucket',
                           'app_name': 'md5',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output'}}
    execution = Execution(input_dict)
    execution.input_size_in_bytes = execution.get_input_size_in_bytes()
    assert execution.total_input_size_in_gb == 1.5832483768463135E-8
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr}, {'Key': randomstr_1}, {'Key': randomstr_2}]})


def test_update_config_ebs_size():
    """ebs_size is given as the 'x' format. The total estimated ebs_size is smaller than 10"""
    randomstr = 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr)
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'tibanna-output',
                                                          'object_key': randomstr}},
                           'output_S3_bucket': 'somebucket',
                           'app_name': 'md5',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'ebs_size': '5.5x'}}
    execution = Execution(input_dict)
    execution.input_size_in_bytes = execution.get_input_size_in_bytes()
    execution.update_config_ebs_size()
    assert execution.cfg.ebs_size == 10
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr}]})


def test_update_config_ebs_size2():
    """ebs_size is given as the 'x' format. The total estimated ebs_size is larger than 10"""
    randomstr = 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr)
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'tibanna-output',
                                                          'object_key': randomstr}},
                           'output_S3_bucket': 'somebucket',
                           'app_name': 'md5',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'ebs_size': '5000000000x'}}
    execution = Execution(input_dict)
    execution.input_size_in_bytes = execution.get_input_size_in_bytes()
    execution.update_config_ebs_size()
    assert execution.cfg.ebs_size == 19
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr}]})


def test_unicorn_input_missing_field():
    """app_name that doesn't exist in benchmark, without instance type, mem, cpu info"""
    input_dict = {'args': {'input_files': {}, 'app_name': 'app_name_not_in_benchmark',
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        UnicornInput(input_dict)
    assert ex
    assert 'app_name' in str(ex.value)


def test_unicorn_input_missing_field2():
    """no app_name without instance type, mem, cpu info"""
    input_dict = {'args': {'input_files': {},
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        UnicornInput(input_dict)
    assert ex
    assert 'app_name' in str(ex.value)


def test_unicorn_input_missing_field3():
    """cwl_main_filename missing for cwl workflow
    (language is not specified which means it is cwl)
    """
    input_dict = {'args': {'input_files': {}, 'app_name': 'bwa-mem',
                           'output_S3_bucket': 'somebucket',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        UnicornInput(input_dict)
    assert ex
    assert 'cwl_main_filename' in str(ex.value)


def test_unicorn_input_missing_field4():
    """neither cwl_directory_url nor cwl_directory_local is provided"""
    input_dict = {'args': {'input_files': {}, 'app_name': 'app_name_not_in_benchmark',
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl'},
                  'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        UnicornInput(input_dict)
    assert ex
    assert 'cwl_directory_url' in str(ex.value)


def test_execution_missing_field5():
    """language is snakemake but command is missing"""
    input_dict = {'args': {'input_files': {}, 'language': 'snakemake',
                           'output_S3_bucket': 'somebucket',
                           'snakemake_main_filename': 'Snakefile',
                           'snakemake_directory_url': 'someurl',
                           'container_image': 'snakemake/snakemake'},
                  'config': {'log_bucket': 'tibanna-output', 'mem': 1, 'cpu': 1}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        Execution(input_dict)
    assert ex
    assert 'command' in str(ex.value)


def test_execution_missing_field6():
    """language is shell but container_image is missing"""
    input_dict = {'args': {'input_files': {}, 'language': 'shell',
                           'output_S3_bucket': 'somebucket',
                           'command': 'some command'},
                  'config': {'log_bucket': 'tibanna-output', 'mem': 1, 'cpu': 1}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        Execution(input_dict)
    assert ex
    assert 'container_image' in str(ex.value)


def test_create_run_json_dict():
    randomstr = 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr)
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'tibanna-output',
                                                          'object_key': randomstr}},
                           'output_S3_bucket': 'somebucket',
                           'app_name': 'md5',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output'}}
    execution = Execution(input_dict)
    runjson = execution.create_run_json_dict()
    assert runjson
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr}]})


def test_create_userdata():
    randomstr = 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr)
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'tibanna-output',
                                                          'object_key': randomstr}},
                           'output_S3_bucket': 'somebucket',
                           'app_name': 'md5',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output'},
                  'jobid': 'myjobid'}
    execution = Execution(input_dict)
    userdata = execution.create_userdata()
    print(userdata)
    assert userdata
    assert 'JOBID=myjobid' in userdata
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr}]})


def test_create_userdata_w_profile():
    randomstr = 'test-' + create_jobid()
    s3 = boto3.client('s3')
    s3.put_object(Body='haha'.encode('utf-8'),
                  Bucket='tibanna-output', Key=randomstr)
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'tibanna-output',
                                                          'object_key': randomstr}},
                           'output_S3_bucket': 'somebucket',
                           'app_name': 'md5',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output'},
                  'jobid': 'myjobid'}
    execution = Execution(input_dict)
    profile = {'access_key': 'haha', 'secret_key': 'lala'}
    userdata = execution.create_userdata(profile=profile)
    print(userdata)
    assert userdata
    assert '-a haha -s lala' in userdata
    # cleanup afterwards
    s3.delete_objects(Bucket='tibanna-output',
                      Delete={'Objects': [{'Key': randomstr}]})


def test_upload_run_json():
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'mem': 1, 'cpu': 1},
                  'jobid': jobid}
    somejson = {'haha': 'lala'}
    execution = Execution(input_dict)
    execution.upload_run_json(somejson)
    s3 = boto3.client('s3')
    res = s3.get_object(Bucket=log_bucket, Key=jobid + '.run.json')
    assert res
    # clean up afterwards
    s3.delete_objects(Bucket=log_bucket,
                      Delete={'Objects': [{'Key': jobid + '.run.json'}]})


def test_launch_args():
    """test creating launch arguments - also test spot_instance"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'mem': 1, 'cpu': 1,
                             'spot_instance': True},
                  'jobid': jobid}
    execution = Execution(input_dict)
    # userdata is required before launch_args is created
    execution.userdata = execution.create_userdata()
    launch_args = execution.launch_args
    print(launch_args)
    assert launch_args
    assert 't3.micro' in str(launch_args)
    assert 'InstanceMarketOptions' in str(launch_args)


def test_launch_and_get_instance_id():
    """test dryrun of ec2 launch"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'mem': 1, 'cpu': 1,
                             'spot_instance': True},
                  'jobid': jobid}
    execution = Execution(input_dict, dryrun=True)
    # userdata is required before launch_args is created
    execution.userdata = execution.create_userdata()
    with pytest.raises(Exception) as ex:
        execution.launch_and_get_instance_id()
    assert 'Request would have succeeded, but DryRun flag is set' in str(ex.value)


def test_ec2_exception_coordinator2():
    """ec2 limit exceptions with 'fail'"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'instance_type': 'c5.4xlarge',
                             'spot_instance': True},
                  'jobid': jobid}
    execution = Execution(input_dict, dryrun=True)
    execution.userdata = execution.create_userdata()
    with pytest.raises(EC2InstanceLimitException) as exec_info:
        execution.ec2_exception_coordinator(fun)()
    assert exec_info


def test_ec2_exception_coordinator3():
    """ec2 exceptions with 'wait_and_retry'"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'instance_type': 'c5.4xlarge',
                             'spot_instance': True,
                             'behavior_on_capacity_limit': 'wait_and_retry'},
                  'jobid': jobid}
    execution = Execution(input_dict, dryrun=True)
    execution.userdata = execution.create_userdata()
    with pytest.raises(EC2InstanceLimitWaitException) as exec_info:
        execution.ec2_exception_coordinator(fun)()
    assert exec_info


def test_ec2_exception_coordinator4():
    """ec2 exceptions with 'other_instance_types'"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'mem': 1, 'cpu': 1,
                             'spot_instance': True,
                             'behavior_on_capacity_limit': 'other_instance_types'},
                  'jobid': jobid}
    execution = Execution(input_dict, dryrun=True)
    assert execution.cfg.instance_type == 't3.micro'
    execution.userdata = execution.create_userdata()
    res = execution.ec2_exception_coordinator(fun)()
    assert res == 'continue'
    assert execution.cfg.instance_type == 't2.micro'
    res = execution.ec2_exception_coordinator(fun)()
    assert res == 'continue'
    assert execution.cfg.instance_type == 't3.small'
    res = execution.ec2_exception_coordinator(fun)()
    assert res == 'continue'
    assert execution.cfg.instance_type == 't2.small'


def test_ec2_exception_coordinator5():
    """ec2 exceptions with 'other_instance_types' but had only one option"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'instance_type': 't2.micro',
                             'spot_instance': True,
                             'behavior_on_capacity_limit': 'other_instance_types'},
                  'jobid': jobid}
    execution = Execution(input_dict, dryrun=True)
    assert execution.cfg.instance_type == 't2.micro'
    execution.userdata = execution.create_userdata()
    with pytest.raises(EC2InstanceLimitException) as exec_info:
        execution.ec2_exception_coordinator(fun)()
    assert 'No more instance type available' in str(exec_info.value)


def test_ec2_exception_coordinator6():
    """ec2 exceptions with 'retry_without_spot'"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'instance_type': 't2.micro',
                             'spot_instance': True,
                             'behavior_on_capacity_limit': 'retry_without_spot'},
                  'jobid': jobid}
    execution = Execution(input_dict, dryrun=True)
    execution.userdata = execution.create_userdata()
    res = execution.ec2_exception_coordinator(fun)()
    assert res == 'continue'
    assert execution.cfg.spot_instance is False  # changed to non-spot
    assert execution.cfg.behavior_on_capacity_limit == 'fail'  # changed to non-spot
    with pytest.raises(EC2InstanceLimitException) as exec_info:
        res = execution.ec2_exception_coordinator(fun)()  # this time, it fails
    assert exec_info


def test_ec2_exception_coordinator7():
    """ec2 exceptions with 'retry_without_spot' without spot instance"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'instance_type': 't2.micro',
                             'behavior_on_capacity_limit': 'retry_without_spot'},
                  'jobid': jobid}
    execution = Execution(input_dict, dryrun=True)
    assert execution.cfg.spot_instance is False
    execution.userdata = execution.create_userdata()
    with pytest.raises(Exception) as exec_info:
        execution.ec2_exception_coordinator(fun)()
    assert "'retry_without_spot' works only with 'spot_instance'" in str(exec_info.value)


def test_ec2_exception_coordinator8():
    """ec2 exceptions with 'other_instance_types' with both instance_type and mem/cpu
    specified"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket, 'instance_type': 't2.micro',
                             'mem': 1, 'cpu': 1,
                             'behavior_on_capacity_limit': 'other_instance_types'},
                  'jobid': jobid}
    execution = Execution(input_dict, dryrun=True)
    assert execution.cfg.instance_type == 't2.micro'
    execution.userdata = execution.create_userdata()
    res = execution.ec2_exception_coordinator(fun)()
    assert res == 'continue'
    assert execution.cfg.instance_type == 't3.micro'
    execution.userdata = execution.create_userdata()
    res = execution.ec2_exception_coordinator(fun)()
    assert res == 'continue'
    assert execution.cfg.instance_type == 't3.small'  # skill t2.micro since it was already tried


def test_ec2_exception_coordinator9():
    """ec2 exceptions with 'other_instance_types' with both instance_type and mem/cpu
    specified"""
    jobid = create_jobid()
    log_bucket = 'tibanna-output'
    input_dict = {'args': {'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': log_bucket,
                             'mem': 2, 'cpu': 1,
                             'behavior_on_capacity_limit': 'other_instance_types'},
                  'jobid': jobid}
    execution = Execution(input_dict, dryrun=True)
    assert execution.cfg.instance_type == 't3.small'
    execution.userdata = execution.create_userdata()
    res = execution.ec2_exception_coordinator(fun)()
    assert res == 'continue'
    assert execution.cfg.instance_type == 't2.small'


def test_upload_workflow_to_s3(run_task_awsem_event_cwl_upload):
    jobid = create_jobid()
    run_task_awsem_event_cwl_upload['jobid'] = jobid
    log_bucket = run_task_awsem_event_cwl_upload['config']['log_bucket']
    unicorn_input = UnicornInput(run_task_awsem_event_cwl_upload)
    upload_workflow_to_s3(unicorn_input)
    s3 = boto3.client('s3')
    res1 = s3.get_object(Bucket=log_bucket, Key=jobid + '.workflow/main.cwl')
    res2 = s3.get_object(Bucket=log_bucket, Key=jobid + '.workflow/child1.cwl')
    res3 = s3.get_object(Bucket=log_bucket, Key=jobid + '.workflow/child2.cwl')
    assert res1
    assert res2
    assert res3
    assert unicorn_input.args.cwl_directory_url == 's3://tibanna-output/' + jobid + '.workflow/'
    # clean up afterwards
    s3.delete_objects(Bucket=log_bucket,
                      Delete={'Objects': [{'Key': jobid + '.workflow/main.cwl'},
                                          {'Key': jobid + '.workflow/child1.cwl'},
                                          {'Key': jobid + '.workflow/child2.cwl'}]})


def test_ec2_cost_estimate_missing_availablity_zone():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_name = "no_availability_zone.postrun.json"
    file_name = os.path.join(dir_path, '..', '..', '..', 'test_json', 'unicorn', file_name)
    with open(file_name, 'r') as file:
        postrunjsonstr = file.read().replace('\n', '')

    postrunjsonobj = json.loads(postrunjsonstr)
    postrunjson = AwsemPostRunJson(**postrunjsonobj)
    assert cost_estimate(postrunjson) == 0.0


def test_ec2_cost_estimate_medium_nonspot():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_name = "medium_nonspot.postrun.json"
    file_name = os.path.join(dir_path, '..', '..', '..', 'test_json', 'unicorn', file_name)
    with open(file_name, 'r') as file:
        postrunjsonstr = file.read().replace('\n', '')

    postrunjsonobj = json.loads(postrunjsonstr)
    postrunjson = AwsemPostRunJson(**postrunjsonobj)
    aws_price_overwrite = {
        'ec2_ondemand_price': 0.0416, 'ebs_root_storage_price': 0.08
        } 
    estimate = cost_estimate(postrunjson, aws_price_overwrite=aws_price_overwrite)
    assert estimate == 0.004384172839506173


def test_ec2_cost_estimate_small_spot():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_name = "small_spot.postrun.json"
    file_name = os.path.join(dir_path, '..', '..', '..', 'test_json', 'unicorn', file_name)
    with open(file_name, 'r') as file:
        postrunjsonstr = file.read().replace('\n', '')

    postrunjsonobj = json.loads(postrunjsonstr)
    postrunjson = AwsemPostRunJson(**postrunjsonobj)
    aws_price_overwrite = {
        'ec2_spot_price': 0.0064, 'ebs_root_storage_price': 0.08
        } 
    estimate = cost_estimate(postrunjson, aws_price_overwrite=aws_price_overwrite)
    assert estimate == 0.0009326172839506175


def test_ec2_cost_estimate_small_spot_gp3_iops():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_name = "small_spot_gp3_iops.postrun.json"
    file_name = os.path.join(dir_path, '..', '..', '..', 'test_json', 'unicorn', file_name)
    with open(file_name, 'r') as file:
        postrunjsonstr = file.read().replace('\n', '')

    postrunjsonobj = json.loads(postrunjsonstr)
    postrunjson = AwsemPostRunJson(**postrunjsonobj)
    aws_price_overwrite = {
        'ec2_spot_price': 0.0064, 'ebs_root_storage_price': 0.08, 'ebs_gp3_iops_price': 0.005
        } 
    estimate = cost_estimate(postrunjson, aws_price_overwrite=aws_price_overwrite)
    assert estimate == 0.0012730879629629633


def test_ec2_cost_estimate_small_spot_io2_iops():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_name = "small_spot_io2_iops.postrun.json"
    file_name = os.path.join(dir_path, '..', '..', '..', 'test_json', 'unicorn', file_name)
    with open(file_name, 'r') as file:
        postrunjsonstr = file.read().replace('\n', '')

    postrunjsonobj = json.loads(postrunjsonstr)
    postrunjson = AwsemPostRunJson(**postrunjsonobj)
    aws_price_overwrite = {
        'ec2_spot_price': 0.0064, 'ebs_root_storage_price': 0.08, 'ebs_storage_price': 0.125, 'ebs_io2_iops_prices': [0.065, 0.0455, 0.03185]
        } 
    estimate = cost_estimate(postrunjson, aws_price_overwrite=aws_price_overwrite)
    assert estimate == 0.029224481481481476
    

def test_check_dependency():
    job_statuses = {
        'running_jobs': ['jid1', 'jid2'],
        'failed_jobs': []
    }
    with mock.patch('tibanna.job.Jobs.status', return_value=job_statuses):
        with pytest.raises(DependencyStillRunningException) as exec_info:
            Execution.check_dependency(job_id=['jid1', 'jid2'])
    assert 'still running' in str(exec_info.value)
    assert 'jid1' in str(exec_info.value)
    assert 'jid2' in str(exec_info.value)


def test_check_dependency_failed():
    job_statuses = {
        'running_jobs': ['jid1'],
        'failed_jobs': ['jid2']
    }
    with mock.patch('tibanna.job.Jobs.status', return_value=job_statuses):
        with pytest.raises(DependencyFailedException) as exec_info:
            Execution.check_dependency(job_id=['jid1', 'jid2'])
    assert 'failed' in str(exec_info.value)
    assert 'jid1' not in str(exec_info.value)
    assert 'jid2' in str(exec_info.value)
