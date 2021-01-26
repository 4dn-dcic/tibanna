import pytest
import copy
from tibanna import awsem
from tibanna.exceptions import MalFormattedRunJsonException


@pytest.fixture
def run_json_inputfile():
    return {
            "class": "File",
            "dir": "somebucket",
            "path": "somefilepath",
            "profile": "",
            "unzip": "",
            "mount": False
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
              "unzip": ""
            },
            "input_bam": {
              "class": "File",
              "dir": "dir2",
              "path": "path2",
              "profile": "",
              "unzip": ""
            },
            "restrict_frags": {
              "class": "File",
              "dir": "dir3",
              "path": "path3",
              "profile": "",
              "unzip": ""
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
    assert r.Log.log_bucket_directory == 'tibanna-output'
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
    assert r.unzip == ''
    assert r.unzip == ''
    r_dict = r.as_dict()
    assert 'class' in r_dict
    assert 'dir' in r_dict
    assert 'path' in r_dict
    assert 'profile' in r_dict
    assert 'unzip' in r_dict
    assert 'unzip' in r_dict
    assert r_dict['class'] == 'File'
    assert r_dict['dir'] == 'somebucket'
    assert r_dict['path'] == 'somefilepath'
    assert r_dict['profile'] == ''
    assert r_dict['unzip'] == ''
    assert r_dict['unzip'] == ''


def test_AwsemRunJsonInputFile_rename_mount_error(run_json_inputfile):
    # rename and mount cannot be used together
    run_json_inputfile['rename'] = 'somerenamedpath'
    run_json_inputfile['mount'] = True
    with pytest.raises(MalFormattedRunJsonException) as ex:
        rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    assert 'rename and mount' in str(ex.value)


def test_AwsemRunJsonInputFile_unzip_mount_error(run_json_inputfile):
    # unzip and mount cannot be used together
    run_json_inputfile['unzip'] = 'gz'
    run_json_inputfile['mount'] = True
    with pytest.raises(MalFormattedRunJsonException) as ex:
        rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    assert 'unzip and mount' in str(ex.value)


def test_AwsemRunJsonInputFile_2d_array_empty_rename_mount_no_error(run_json_inputfile):
    # rename is not nul but should not raise an error
    run_json_inputfile['path'] = [['path1', 'path2'], ['path3', 'path4']]
    run_json_inputfile['rename'] = [[], []]
    run_json_inputfile['mount'] = True
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    assert rj_infile.rename == [[], []]


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


def test_file2cwlfile():
    cwlfile = awsem.file2cwlfile('somedir/somefile', 'parentdir', '')
    assert cwlfile == {'path': 'parentdir/somedir/somefile', 'class': 'File'}


def test_file2wdlfile():
    wdlfile = awsem.file2wdlfile('somedir/somefile', 'parentdir', '')
    assert wdlfile == 'parentdir/somedir/somefile'


def test_file2cwlfile_unzip():
    cwlfile = awsem.file2cwlfile('somedir/somefile.gz', 'parentdir', 'gz')
    assert cwlfile == {'path': 'parentdir/somedir/somefile', 'class': 'File'}


def test_file2cwlfile_unzip2():
    cwlfile = awsem.file2cwlfile('somedir/somefile.bz2', 'parentdir', 'bz2')
    assert cwlfile == {'path': 'parentdir/somedir/somefile', 'class': 'File'}


def test_file2cwlfile_unzip3():
    cwlfile = awsem.file2cwlfile('somedir/somefile.gz', 'parentdir/', '')
    assert cwlfile == {'path': 'parentdir/somedir/somefile.gz', 'class': 'File'}


def test_file2wdlfile_unzip():
    wdlfile = awsem.file2wdlfile('somedir/somefile.gz', 'parentdir', 'gz')
    assert wdlfile == 'parentdir/somedir/somefile'


def test_file2wdlfile_unzip2():
    wdlfile = awsem.file2wdlfile('somedir/somefile.bz2', 'parentdir', 'bz2')
    assert wdlfile == 'parentdir/somedir/somefile'


def test_file2wdlfile_unzip2():
    wdlfile = awsem.file2wdlfile('somedir/somefile.bz2', 'parentdir/', '')
    assert wdlfile == 'parentdir/somedir/somefile.bz2'


def test_AwsemRunJsonInputFile_as_dict_as_cwl_input(run_json_inputfile):
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    cwlinput = rj_infile.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == {'path': '/data1/input/somefilepath', 'class': 'File'}


def test_AwsemRunJsonInputFile_as_dict_as_cwl_input_mount(run_json_inputfile):
    run_json_inputfile['mount'] = True
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    cwlinput = rj_infile.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == {'path': '/data1/input-mounted-somebucket/somefilepath', 'class': 'File'}


def test_AwsemRunJsonInputFile_as_dict_as_cwl_rename(run_json_inputfile):
    run_json_inputfile['rename'] = 'somerenamedpath'
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    cwlinput = rj_infile.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == {'path': '/data1/input/somerenamedpath', 'class': 'File'}


def test_AwsemRunJsonInputFile_as_dict_as_wdl_input(run_json_inputfile):
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    wdlinput = rj_infile.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == '/data1/input/somefilepath'


def test_AwsemRunJsonInputFile_as_dict_as_wdl_input_mount(run_json_inputfile):
    run_json_inputfile['mount'] = True
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    wdlinput = rj_infile.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == '/data1/input-mounted-somebucket/somefilepath'


def test_AwsemRunJsonInputFile_as_dict_as_wdl_rename(run_json_inputfile):
    run_json_inputfile['rename'] = 'somerenamedpath'
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    wdlinput = rj_infile.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == '/data1/input/somerenamedpath'


def test_AwsemRunJsonInput_as_dict_as_cwl_input(run_json_input):
    rj_in = awsem.AwsemRunJsonInput(**run_json_input)
    cwlinput = rj_in.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == {'n': 2,
                        'chromsize': {'path': '/data1/input/path1', 'class': 'File'},
                        'input_bam': {'path': '/data1/input/path2', 'class': 'File'},         
                        'restrict_frags': {'path': '/data1/input/path3', 'class': 'File'}}


def test_AwsemRunJsonInput_as_dict_as_wdl_input(run_json_input):
    rj_in = awsem.AwsemRunJsonInput(**run_json_input)
    wdlinput = rj_in.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == {'n': 2,
                        'chromsize': '/data1/input/path1',
                        'input_bam': '/data1/input/path2',
                        'restrict_frags': '/data1/input/path3'}


def test_AwsemRunJsonInputFile_as_dict_as_cwl_array(run_json_inputfile):
    run_json_inputfile['path'] = ['path1', 'path2']
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    cwlinput = rj_infile.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == [{'path': '/data1/input/path1', 'class': 'File'},
                        {'path': '/data1/input/path2', 'class': 'File'}]


def test_AwsemRunJsonInputFile_as_dict_as_cwl_2d_array(run_json_inputfile):
    run_json_inputfile['path'] = [['path1', 'path2'], ['path3', 'path4']]
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    cwlinput = rj_infile.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == [[{'path': '/data1/input/path1', 'class': 'File'},
                         {'path': '/data1/input/path2', 'class': 'File'}],
                        [{'path': '/data1/input/path3', 'class': 'File'},
                         {'path': '/data1/input/path4', 'class': 'File'}]]


def test_AwsemRunJsonInputFile_as_dict_as_cwl_2d_array_rename(run_json_inputfile):
    run_json_inputfile['path'] = [['path1', 'path2'], ['path3', 'path4']]
    run_json_inputfile['rename'] = [['renamed1', 'renamed2'], ['renamed3', 'renamed4']]
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    cwlinput = rj_infile.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == [[{'path': '/data1/input/renamed1', 'class': 'File'},
                         {'path': '/data1/input/renamed2', 'class': 'File'}],
                        [{'path': '/data1/input/renamed3', 'class': 'File'},
                         {'path': '/data1/input/renamed4', 'class': 'File'}]]


def test_AwsemRunJsonInputFile_as_dict_as_cwl_2d_array_unzip(run_json_inputfile):
    run_json_inputfile['path'] = [['path1.gz', 'path2.gz'], ['path3.gz', 'path4.gz']]
    run_json_inputfile['unzip'] = 'gz'
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    cwlinput = rj_infile.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == [[{'path': '/data1/input/path1', 'class': 'File'},
                         {'path': '/data1/input/path2', 'class': 'File'}],
                        [{'path': '/data1/input/path3', 'class': 'File'},
                         {'path': '/data1/input/path4', 'class': 'File'}]]


def test_AwsemRunJsonInputFile_as_dict_as_cwl_2d_array_unzip2(run_json_inputfile):
    run_json_inputfile['path'] = [['path1.bz2', 'path2.bz2'], ['path3.bz2', 'path4.bz2']]
    run_json_inputfile['unzip'] = 'bz2'
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    cwlinput = rj_infile.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == [[{'path': '/data1/input/path1', 'class': 'File'},
                         {'path': '/data1/input/path2', 'class': 'File'}],
                        [{'path': '/data1/input/path3', 'class': 'File'},
                         {'path': '/data1/input/path4', 'class': 'File'}]]


def test_AwsemRunJsonInputFile_as_dict_as_cwl_2d_array_mount(run_json_inputfile):
    run_json_inputfile['path'] = [['path1', 'path2'], ['path3', 'path4']]
    run_json_inputfile['mount'] = True
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    cwlinput = rj_infile.as_dict_as_cwl_input('/data1/input/', '/data1/input-mounted-')
    assert cwlinput == [[{'path': '/data1/input-mounted-somebucket/path1', 'class': 'File'},
                         {'path': '/data1/input-mounted-somebucket/path2', 'class': 'File'}],
                        [{'path': '/data1/input-mounted-somebucket/path3', 'class': 'File'},
                         {'path': '/data1/input-mounted-somebucket/path4', 'class': 'File'}]]


def test_AwsemRunJsonInputFile_as_dict_as_wdl_array(run_json_inputfile):
    run_json_inputfile['path'] = ['path1', 'path2']
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    wdlinput = rj_infile.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == ['/data1/input/path1',
                        '/data1/input/path2']


def test_AwsemRunJsonInputFile_as_dict_as_wdl_2d_array(run_json_inputfile):
    run_json_inputfile['path'] = [['path1', 'path2'], ['path3', 'path4']]
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    wdlinput = rj_infile.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == [['/data1/input/path1',
                         '/data1/input/path2'],
                        ['/data1/input/path3',
                         '/data1/input/path4']]


def test_AwsemRunJsonInputFile_as_dict_as_wdl_2d_array_rename(run_json_inputfile):
    run_json_inputfile['path'] = [['path1', 'path2'], ['path3', 'path4']]
    run_json_inputfile['rename'] = [['renamed1', 'renamed2'], ['renamed3', 'renamed4']]
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    wdlinput = rj_infile.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == [['/data1/input/renamed1',
                         '/data1/input/renamed2'],
                        ['/data1/input/renamed3',
                         '/data1/input/renamed4']]


def test_AwsemRunJsonInputFile_as_dict_as_wdl_2d_array_unzip(run_json_inputfile):
    run_json_inputfile['path'] = [['path1.gz', 'path2.gz'], ['path3.gz', 'path4.gz']]
    run_json_inputfile['unzip'] = 'gz'
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    wdlinput = rj_infile.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == [['/data1/input/path1',
                         '/data1/input/path2'],
                        ['/data1/input/path3',
                         '/data1/input/path4']]


def test_AwsemRunJsonInputFile_as_dict_as_wdl_2d_array_unzip2(run_json_inputfile):
    run_json_inputfile['path'] = [['path1.bz2', 'path2.bz2'], ['path3.bz2', 'path4.bz2']]
    run_json_inputfile['unzip'] = 'bz2'
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    wdlinput = rj_infile.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == [['/data1/input/path1',
                         '/data1/input/path2'],
                        ['/data1/input/path3',
                         '/data1/input/path4']]


def test_AwsemRunJsonInputFile_as_dict_as_wdl_2d_array_mount(run_json_inputfile):
    run_json_inputfile['path'] = [['path1', 'path2'], ['path3', 'path4']]
    run_json_inputfile['mount'] = True
    rj_infile = awsem.AwsemRunJsonInputFile(**run_json_inputfile)
    wdlinput = rj_infile.as_dict_as_wdl_input('/data1/input/', '/data1/input-mounted-')
    assert wdlinput == [['/data1/input-mounted-somebucket/path1',
                         '/data1/input-mounted-somebucket/path2'],
                        ['/data1/input-mounted-somebucket/path3',
                         '/data1/input-mounted-somebucket/path4']]


def test_AwsemPostRunJsonOutput_alt_output_target(postrun_json_output):
    postrun_json_output['output_target'] = {'arg1': 'target1', 'arg2': 'target2'}
    postrun_json_output['alt_cond_output_argnames'] = {'arg2': ['arg2a', 'arg2b']}
    prjo = awsem.AwsemPostRunJsonOutput(**postrun_json_output)
    assert prjo.alt_output_target(['arg1', 'arg2b']) == {'arg1': 'target1', 'arg2b': 'target2'}


def test_file_uri_cwl_wdl_error():
    rji_dict = {'file:///data1/input/file1': {'path': 'somefile', 'dir': 'somebucket', 'mount': False}}
    runjson_input = awsem.AwsemRunJsonInput(**{'Input_files_data': rji_dict})
    with pytest.raises(MalFormattedRunJsonException) as ex:
        runjson_input.check_input_files_key_compatibility('cwl')
    assert 'argument name for CWL' in str(ex.value)
    with pytest.raises(MalFormattedRunJsonException) as ex:
        runjson_input.check_input_files_key_compatibility('wdl')
    assert 'argument name for CWL' in str(ex.value)
    runjson_input.check_input_files_key_compatibility('shell')
    runjson_input.check_input_files_key_compatibility('snakemake')
