import pytest
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
        "Input_parameters": {}
    }

@pytest.fixture
def run_json_app():
    return {
        "App_name": "someapp",
        "App_version": "v1.0"
    }


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

