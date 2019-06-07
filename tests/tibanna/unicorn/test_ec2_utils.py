from tibanna.ec2_utils import (
    UnicornInput,
    Args,
    Config,
    Execution,
    upload_workflow_to_s3
)
from tibanna.utils import create_jobid
from tibanna.exceptions import (
    MissingFieldInInputJsonException
)
import boto3
import pytest


def test_args():
    input_dict = {'args': {'input_files': {}, 'output_S3_bucket': 'somebucket', 'app_name': 'someapp'}}
    args = Args(**input_dict['args'])
    args_dict = args.as_dict()
    assert 'input_files' in args_dict
    assert 'app_name' in args_dict
    assert args_dict['app_name'] == 'someapp'

def test_args_missing_field():
    input_dict = {'args': {'input_files': {}, 'app_name': 'someapp'}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        args = Args(**input_dict['args'])
    assert ex
    assert 'output_S3_bucket' in str(ex.value)

def test_config():
    input_dict = {'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    cfg = Config(**input_dict['config'])
    cfg_dict = cfg.as_dict()
    assert 'log_bucket' in cfg_dict
    assert 'shutdown_min' in cfg_dict
    assert cfg_dict['shutdown_min'] == 30

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
    language is wdl this time"""
    input_dict = {'args': {'input_files': {}, 'language': 'wdl',
                           'output_S3_bucket': 'somebucket',
                           'wdl_main_filename': 'main.wdl',
                           'wdl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'instance_type': 't2.nano'}}
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
                           'container_image': 'quay.io/snakemake/snakemake'},
                  'config': {'log_bucket': 'tibanna-output', 'mem': 1, 'cpu': 1}}
    execution = Execution(input_dict)
    unicorn_dict = execution.input_dict
    print(execution.instance_type_list)
    assert 'args' in unicorn_dict
    assert 'config' in unicorn_dict
    assert 'instance_type' in unicorn_dict['config']
    assert unicorn_dict['config']['instance_type'] == 't3.micro'

def test_execution_benchmark():
    """mem and cpu are provided but not app_name or instance_type,
    which should be fine.
    language is snakemake this time"""
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'soos-4dn-bucket',
                                                          'object_key': 'haha'}},
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

def test_unicorn_input_missing_field():
    """app_name that doesn't exist in benchmark, without instance type, mem, cpu info"""
    input_dict = {'args': {'input_files': {}, 'app_name': 'app_name_not_in_benchmark',
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        unicorn_input = UnicornInput(input_dict)
    assert ex
    assert 'app_name' in str(ex.value)

def test_unicorn_input_missing_field2():
    "no app_name without instance type, mem, cpu info"""
    input_dict = {'args': {'input_files': {},
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        unicorn_input = UnicornInput(input_dict)
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
        unicorn_input = UnicornInput(input_dict)
    assert ex
    assert 'cwl_main_filename' in str(ex.value)

def test_unicorn_input_missing_field4():
    """neither cwl_directory_url nor cwl_directory_local is provided"""
    input_dict = {'args': {'input_files': {}, 'app_name': 'app_name_not_in_benchmark',
                           'output_S3_bucket': 'somebucket',
                           'cwl_main_filename': 'main.cwl'},
                  'config': {'log_bucket': 'tibanna-output', 'shutdown_min': 30}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        unicorn_input = UnicornInput(input_dict)
    assert ex
    assert 'cwl_directory_url' in str(ex.value)

def test_execution_missing_field5():
    """language is snakemake but command is missing"""
    input_dict = {'args': {'input_files': {}, 'language': 'snakemake',
                           'output_S3_bucket': 'somebucket',
                           'snakemake_main_filename': 'Snakefile',
                           'snakemake_directory_url': 'someurl',
                           'container_image': 'quay.io/snakemake/snakemake'},
                  'config': {'log_bucket': 'tibanna-output', 'mem': 1, 'cpu': 1}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        execution = Execution(input_dict)
    assert ex
    assert 'command' in str(ex.value)

def test_execution_missing_field6():
    """language is shell but container_image is missing"""
    input_dict = {'args': {'input_files': {}, 'language': 'shell',
                           'output_S3_bucket': 'somebucket',
                           'command': 'some command'},
                  'config': {'log_bucket': 'tibanna-output', 'mem': 1, 'cpu': 1}}
    with pytest.raises(MissingFieldInInputJsonException) as ex:
        execution = Execution(input_dict)
    assert ex
    assert 'container_image' in str(ex.value)

def test_create_run_json_dict():
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'soos-4dn-bucket',
                                                          'object_key': 'haha'}},
                           'output_S3_bucket': 'somebucket',
                           'app_name': 'md5',
                           'cwl_main_filename': 'md5.cwl',
                           'cwl_directory_url': 'someurl'},
                  'config': {'log_bucket': 'tibanna-output'}}
    execution = Execution(input_dict)
    runjson = execution.create_run_json_dict()
    assert runjson

def test_create_userdata():
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'soos-4dn-bucket',
                                                          'object_key': 'haha'}},
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

def test_create_userdata_w_profile():
    input_dict = {'args': {'input_files': {'input_file': {'bucket_name': 'soos-4dn-bucket',
                                                          'object_key': 'haha'}},
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
