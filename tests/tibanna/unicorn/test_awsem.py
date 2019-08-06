import pytest
import copy
from tibanna import awsem


@pytest.fixture
def run_json_inputfile():
    return {
            "class": "File",
            "dir": "somebucket",
            "path": "somefilepath",
            "profile": "",
            "rename": ""
    }

@pytest.fixture
def run_json_input():
    return {
        "Env": {},
        "Input_files_data": {
            "chromsize": {
              "class": "File",
              "dir": "dir1",
              "path": "path1",
              "profile": "",
              "rename": ""
            },
            "input_bam": {
              "class": "File",
              "dir": "dir2",
              "path": "path2",
              "profile": "",
              "rename": ""
            },
            "restrict_frags": {
              "class": "File",
              "dir": "dir3",
              "path": "path3",
              "profile": "",
              "rename": ""
            },
        },
        "Secondary_files_data": {},
        "Input_parameters": {'n': 2}
    }

@pytest.fixture
def run_json_app():
    return {
        "App_name": "someapp",
        "App_version": "v1.0"
    }

@pytest.fixture
def run_json_output():
    return {
        "output_bucket_directory": "somebucket",
        "output_target": {
            "file://tests/awsf/haha": "shelltest-haha",
            "file://tests/awsf/mydir": "shelltest-mydir"
        },
        "secondary_output_target": {},
        "alt_cond_output_argnames": {}
    }

@pytest.fixture
def run_json_job(run_json_app, run_json_input, run_json_output):
    return {
        'App': run_json_app,
        'Input': run_json_input,
        'Log': {"log_bucket_directory": "tibanna-output"},
        'JOBID': "J55BCqwHx6N5",
        'Output': run_json_output,
        'start_time': "20180430-18:50:18-UTC"
    }

@pytest.fixture
def run_json_config():
    return {
        'log_bucket': 'somelogbucket',
        'instance_type': 't3.medium'
    }

@pytest.fixture
def run_json(run_json_job, run_json_config):
    return {
        'Job': run_json_job,
        'config': run_json_config
    }

@pytest.fixture
def postrun_json_output(run_json_output, postrun_json_outputfile):
    json = copy.deepcopy(run_json_output)
    json.update({'Output files': {'pairs': postrun_json_outputfile}})
    return json

@pytest.fixture
def postrun_json_outputfile():
    return {
        "basename": "out.pairs.gz",
        "checksum": "sha1$7625d7b5cc4269408e6c08e691c9e9401668ee13",
        "class": "File",
        "location": "file:///data1/out/out.pairs.gz",
        "md5sum": "1a892518a073aa8e2b9205cf160594f4",
        "path": "/data1/out/out.pairs.gz",
        "secondaryFiles": [
          {
            "basename": "out.pairs.gz.px2",
            "checksum": "sha1$4b1384e757ddcb1b216e0bc3c778d5657c94ed5c",
            "class": "File",
            "location": "file:///data1/out/out.pairs.gz.px2",
            "md5sum": "494fae3d6567c1f7ed5fd2e16238d95f",
            "path": "/data1/out/out.pairs.gz.px2",
            "size": 12931458,
            "target": "somepairs.pairs.gz.px2"
          }
        ],
        "size": 2282418874,
        "target": "somepairs.pairs.gz"
    }

@pytest.fixture
def postrun_json_job(run_json_job):
    json = copy.deepcopy(run_json_job)
    json.update({
        "end_time": "20190531-04:24:55-UTC",
        "filesystem": "/dev/nvme1n1",
        "instance_id": "i-08d1c54ed1f74ab36",
        "status": "0",
        "total_input_size": "2.2G",
        "total_output_size": "4.2G",
        "total_tmp_size": "7.4G",
        "Metrics": {
            "max_mem_used_MB": 13250.1,
            "min_mem_available_MB": 18547.51953125,
            "total_mem_MB": 31797.67578125,
            "max_mem_utilization_percent": 41.67020363737768,
            "max_cpu_utilization_percent": 99.4,
            "max_disk_space_utilization_percent": 40.5262269248086,
            "max_disk_space_used_GB": 15
        }
    })
    return json

@pytest.fixture
def postrun_json(postrun_json_job, run_json_config):
    return {
        'Job': postrun_json_job,
        'config': run_json_config,
        'commands': ['command1', 'command2']
    }

def test_PostRunJson(postrun_json):
    r = awsem.AwsemPostRunJson(**postrun_json)
    assert r.Job.filesystem == "/dev/nvme1n1"
    assert r.config.instance_type == 't3.medium'
    assert len(r.commands) == 2
    r_dict = r.as_dict()
    r_dict['Job']['Metrics']['max_disk_space_used_GB'] == 30
    assert r_dict['commands'][1] == 'command2'
    assert r_dict['Job']['total_output_size'] == '4.2G'
    assert r.Job.Metrics['max_disk_space_used_GB'] == 15

def test_PostRunJsonJob(postrun_json_job):
    r = awsem.AwsemPostRunJsonJob(**postrun_json_job)
    assert r.end_time == "20190531-04:24:55-UTC"
    assert r.Metrics['max_cpu_utilization_percent'] == 99.4
    assert r.status == '0'
    r_dict = r.as_dict()
    r_dict['total_input_size'] = '20G'
    assert r.total_input_size == '2.2G'  # changing r_dict shouldn't affect r
    assert r_dict['total_tmp_size'] == '7.4G'
    assert r_dict['Metrics']['max_mem_used_MB'] == 13250.1

def test_PostRunJsonOutput(postrun_json_output):
    r = awsem.AwsemPostRunJsonOutput(**postrun_json_output)
    assert len(r.Output_files_) == 1
    assert r.Output_files_['pairs'].path == '/data1/out/out.pairs.gz'
    assert r.Output_files_['pairs'].secondaryFiles[0].size == 12931458
    r_dict = r.as_dict()
    assert r_dict['Output files']['pairs']['class'] == 'File'
    assert r_dict['Output files']['pairs']['size'] == 2282418874
    assert r_dict['Output files']['pairs']['secondaryFiles'][0]['basename'] == "out.pairs.gz.px2"
    assert r_dict['output_bucket_directory'] == "somebucket"  # inherited from runjson

def test_PostRunJsonOutputFile(postrun_json_outputfile):
    r = awsem.AwsemPostRunJsonOutputFile(**postrun_json_outputfile)
    assert r.basename == "out.pairs.gz"
    assert r.class_ == 'File'
    assert r.target == 'somepairs.pairs.gz'
    assert r.secondaryFiles[0].target == 'somepairs.pairs.gz.px2'

def test_RunJson(run_json):
    r = awsem.AwsemRunJson(**run_json)
    assert r.Job.start_time == "20180430-18:50:18-UTC"
    assert r.config.log_bucket == 'somelogbucket'
    r_dict = r.as_dict()
    assert 'Job' in r_dict
    assert r_dict['Job']['Input']['Input_files_data']['chromsize']['path'] == 'path1'
    r_dict['Job']['Input']['Input_files_data']['chromsize']['path'] = 'someotherpath'
    assert r.Job.Input.Input_files_data['chromsize'].path == 'path1'  # changing r_dict shouldn't affect r

def test_RunJsonJob(run_json_job):
    r = awsem.AwsemRunJsonJob(**run_json_job)
    r_dict = r.as_dict()
    r_dict['App']['App_name'] = 'someotherapp'
    assert r_dict['App']['App_name'] == 'someotherapp'
    assert r_dict['Input']['Input_files_data']['restrict_frags']['path'] == 'path3'
    assert r.App.App_name == 'someapp'  # changing r_dict shoudn't affect r
    assert r.Input.Input_parameters['n'] == 2
    assert r.Output.output_bucket_directory == 'somebucket'
    assert r.Log['log_bucket_directory'] == 'tibanna-output'
    assert r.JOBID == "J55BCqwHx6N5"

def test_RunJsonOutput(run_json_output):
    r = awsem.AwsemRunJsonOutput(**run_json_output)
    assert r.output_bucket_directory == 'somebucket'
    assert len(r.output_target) == 2
    r_dict = r.as_dict()
    assert r_dict['output_target']["file://tests/awsf/haha"] == "shelltest-haha"
    r_dict['output_target'] = {}
    assert len(r.output_target) == 2  # changing r_dict shouldn't affect r

def test_RunJsonInputFile(run_json_inputfile):
    r = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    assert hasattr(r, 'class_')
    assert hasattr(r, 'dir_')
    assert hasattr(r, 'path')
    assert hasattr(r, 'profile')
    assert hasattr(r, 'unzip')  # default '' if omitted
    assert r.class_ == 'File'
    assert r.dir_ == 'somebucket'
    assert r.path == 'somefilepath'
    assert r.profile == ''
    assert r.rename == ''
    assert r.unzip == ''
    r_dict = r.as_dict()
    assert 'class' in r_dict
    assert 'dir' in r_dict
    assert 'path' in r_dict
    assert 'profile' in r_dict
    assert 'rename' in r_dict
    assert 'unzip' in r_dict
    assert r_dict['class'] == 'File'
    assert r_dict['dir'] == 'somebucket'
    assert r_dict['path'] == 'somefilepath'
    assert r_dict['profile'] == ''
    assert r_dict['rename'] == ''
    assert r_dict['unzip'] == ''

def test_RunJsonInput(run_json_input):
    r = awsem.AwsemRunJsonInput(**run_json_input)
    assert len(r.Input_files_data) == 3
    assert r.Input_files_data['input_bam'].dir_ == 'dir2'
    assert r.Env == {}

def test_RunJsonApp(run_json_app):
    r = awsem.AwsemRunJsonApp(**run_json_app)
    assert r.App_name == 'someapp'
    assert r.App_version == 'v1.0'
    r_dict = r.as_dict()
    assert r_dict['App_name'] == 'someapp'
    r_dict['App_version'] = 'lalala'
    assert r.App_version == 'v1.0'  # changing r_dict shouldn't affect r

