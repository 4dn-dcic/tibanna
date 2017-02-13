from core import utils
import pytest
from conftest import valid_env


@pytest.fixture
def sbg_project():
    return "4dn-dcic/dev"


@pytest.fixture
def json_request():
    return {
          "input_files": [
            {
              "bucket_name": "encoded-4dn-files",
              "object_key": "4DNFI067AFHV.fastq.gz",
              "uuid": "46e82a90-49e5-4c33-afab-9ec90d65cca1",
              "workflow_argument_name": "fastq1"
            },
            {
              "bucket_name": "encoded-4dn-files",
              "object_key": "4DNFI067AFHX.fastq.gz",
              "uuid": "46e82a90-49e5-4c33-afab-9ec90d65cca2",
              "workflow_argument_name": "fastq2"
            },
            {
              "bucket_name": "encoded-4dn-files",
              "object_key": "4DNFIZQZ39L9.bwaIndex.tgz",
              "uuid": "1f53df95-4cf3-41cc-971d-81bb16c486dd",
              "workflow_argument_name": "bwa_index"
            }
          ],
          "workflow_uuid": "02d636b9-d82d-4da9-950c-2ca994a0943e",
          "app_name": "hi-c-processing-parta",
          "parameters": {
            "nThreads": 8,
            "teststring": "test",
          }
        }


@pytest.fixture
def workflow_event_data():
    return {"workflow": {"import_id_list": ["FHtnXozBk1C5Fyp2dRmSa2yhFCBBoEcN"],
                         "app_name": "md5",
                         "task_id": "",
                         "task_input": {"app": "4dn-dcic/dev/md5",
                                        "project": "4dn-dcic/dev",
                                        "name": "md5",
                                        "inputs": {"input_file": {"class": "File",
                                                                  "name": "4DNFI7RAJFJ4.fasta.gz",
                                                                  "path": "5877fc32e4b0f31cb4bc37a1"}}},
                         "volume_list": [{"id": "4dn-labor/4dn_s32588y8f6", "name": "4dn_s32588y8f6"}],
                         "header": {"X-SBG-Auth-Token": "1234", "Content-type": "application/json"},
                         "token": "1234", "export_report": [], "project_id": "4dn-dcic/dev",
                         "export_id_list": [], "output_volume_id": "4dn-labor/4dn_s32588y8f7"}}


def test_create_ff_meta_base_sbg_data(json_request):
    app_name = json_request['app_name']
    sbg = utils.create_sbg_workflow(app_name)
    parameters, input_files = utils.to_sbg_workflow_args(json_request['parameters'])
    ff_meta = utils.create_ffmeta(sbg, json_request['workflow_uuid'],
                                  input_files, parameters)

    assert ff_meta.title.startswith(app_name)
    assert ff_meta.input_files == input_files
    assert ff_meta.parameters == parameters


def test_create_ff_meta_pulls_data_from_sbg_object(workflow_event_data, json_request):
    sbg = utils.create_sbg_workflow(**workflow_event_data['workflow'])
    parameters, input_files = utils.to_sbg_workflow_args(json_request['parameters'])
    ff_meta = utils.create_ffmeta(sbg, json_request['workflow_uuid'],
                                  input_files, parameters)
    assert ff_meta
    assert ff_meta.title.startswith(sbg.app_name)
    assert ff_meta.input_files == input_files
    assert ff_meta.parameters == parameters
    assert ff_meta.sbg_import_ids == sbg.import_id_list
    vols_in_test_data = [item['name'] for item in sbg.volume_list]
    for vol in ff_meta.sbg_mounted_volume_ids:
        assert vol in vols_in_test_data
    assert ff_meta.sbg_task_id == sbg.task_id


def test_to_sbg_workflow_args(json_request):
    sbg_args, sbg_input = utils.to_sbg_workflow_args(json_request['parameters'])
    assert sbg_args[0]['workflow_argument_name'] == 'nThreads'
    assert sbg_args[0]['value'] == 8
    assert sbg_args[1]['workflow_argument_name'] == 'teststring'
    assert sbg_args[1]['value'] == 'test'
    assert len(sbg_args) == 2
    assert sbg_input == []


@valid_env
def test_sbg_api_gets_keys_by_default():
    api = utils.SBGAPI()
    assert api
    assert api.token
    assert api.header


@valid_env
@pytest.mark.webtest
def test_read_s3():
    filename = '__test_data/test_file.txt'
    read = utils.read_s3(filename)
    assert read.strip() == 'thisisatest'


@valid_env
@pytest.mark.webtest
def test_read_s3_zip():
    filename = '__test_data/fastqc_report.zip'
    files = utils.read_s3_zipfile(filename, ['summary.txt', 'fastqc_data.txt'])
    assert files['summary.txt']
    assert files['fastqc_data.txt']
    assert files['summary.txt'].startswith('PASS')


@valid_env
@pytest.mark.webtest
def test_unzip_s3_to_s3():
    prefix = '__test_data/extracted'
    filename = '__test_data/fastqc_report.zip'
    utils.s3_delete_dir(prefix)

    # ensure this thing was deleted
    # if no files there will be no Contents in response
    objs = utils.s3_read_dir(prefix)
    assert [] == objs.get('Contents', [])

    # now copy to that dir we just deleted
    retfile_list = ['summary.txt', 'fastqc_data.txt']
    ret_files = utils.unzip_s3_to_s3(filename, prefix, retfile_list)
    assert 2 == len(ret_files.keys())

    objs = utils.s3_read_dir(prefix)
    assert objs.get('Contents', None)


@valid_env
@pytest.mark.webtest
def test_create_sbg_workflow(sbg_project, sbg_keys):
    sbg = utils.SBGWorkflowRun(app_name='md5', token=sbg_keys, project_id=sbg_project)
    assert sbg.header
    assert sbg.header['X-SBG-Auth-Token'] == sbg_keys
    assert sbg.app_name == 'md5'


def test_create_sbg_workflow_from_event_parameter(workflow_event_data):
    wf = workflow_event_data['workflow']
    sbg = utils.create_sbg_workflow(**wf)
    assert sbg.export_id_list == wf['export_id_list']
    assert sbg.volume_list == wf['volume_list']
    assert sbg.import_id_list == wf['import_id_list']
    assert sbg.project_id == wf['project_id']
    assert sbg.app_name == wf['app_name']
    assert sbg.header == wf['header']
    assert sbg.task_input.__dict__ == wf['task_input']
    assert sbg.output_volume_id == wf['output_volume_id']


def test_create_workflowrun_from_event_parameter(ff_meta_event_data):
    meta = ff_meta_event_data['ff_meta']
    ff_wfr = utils.WorkflowRunMetadata(**meta)
    assert ff_wfr


def test_sbg_workflow_as_dict_clears_secrets(workflow_event_data):
    wf = workflow_event_data['workflow']
    sbg = utils.create_sbg_workflow(**wf)
    sbg_dict = sbg.as_dict()
    assert not sbg_dict.get('header')
    assert not sbg_dict.get('token')
    assert sbg_dict.get('output_volume_id') == wf['output_volume_id']
