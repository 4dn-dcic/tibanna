from core import sbg_utils, ff_utils
from core.utils import Tibanna, ensure_list, powerup
import pytest
from conftest import valid_env
import mock
from core.utils import StillRunningException


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


def test_create_ff_meta_base_sbg_data(json_request, sbg_keys):
    app_name = json_request['app_name']
    sbg = sbg_utils.create_sbg_workflow(app_name, sbg_keys)
    parameters, input_files = sbg_utils.to_sbg_workflow_args(json_request['parameters'])
    ff_meta = ff_utils.create_ffmeta(sbg, json_request['workflow_uuid'],
                                     input_files, parameters)

    assert ff_meta.title.startswith(app_name)
    assert ff_meta.input_files == input_files
    assert ff_meta.parameters == parameters


def test_create_ff_meta_pulls_data_from_sbg_object(workflow_event_data, json_request):
    sbg = sbg_utils.create_sbg_workflow(**workflow_event_data['workflow'])
    parameters, input_files = sbg_utils.to_sbg_workflow_args(json_request['parameters'])
    ff_meta = ff_utils.create_ffmeta(sbg, json_request['workflow_uuid'],
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
    sbg_args, sbg_input = sbg_utils.to_sbg_workflow_args(json_request['parameters'])
    assert sbg_args[0]['workflow_argument_name'] == 'nThreads'
    assert sbg_args[0]['value'] == 8
    assert sbg_args[1]['workflow_argument_name'] == 'teststring'
    assert sbg_args[1]['value'] == 'test'
    assert len(sbg_args) == 2
    assert sbg_input == []


@valid_env
@pytest.mark.webtest
def test_read_s3(s3_utils):
    filename = '__test_data/test_file.txt'
    read = s3_utils.read_s3(filename)
    assert read.strip() == 'thisisatest'


@valid_env
@pytest.mark.webtest
def test_get_file_size(s3_utils):
    filename = '__test_data/test_file.txt'
    size = s3_utils.get_file_size(filename)
    assert size == 12


@valid_env
@pytest.mark.webtest
def test_get_file_size_in_bg(s3_utils):
    filename = '__test_data/test_file.txt'
    size = s3_utils.get_file_size(filename, add_gb=2, size_in_gb=True)
    assert size == 2


@valid_env
@pytest.mark.webtest
def test_read_s3_zip(s3_utils):
    filename = '__test_data/fastqc_report.zip'
    files = s3_utils.read_s3_zipfile(filename, ['summary.txt', 'fastqc_data.txt'])
    assert files['summary.txt']
    assert files['fastqc_data.txt']
    assert files['summary.txt'].startswith('PASS')


@valid_env
@pytest.mark.webtest
def test_unzip_s3_to_s3(s3_utils):
    prefix = '__test_data/extracted'
    filename = '__test_data/fastqc_report.zip'
    s3_utils.s3_delete_dir(prefix)

    # ensure this thing was deleted
    # if no files there will be no Contents in response
    objs = s3_utils.s3_read_dir(prefix)
    assert [] == objs.get('Contents', [])

    # now copy to that dir we just deleted
    retfile_list = ['summary.txt', 'fastqc_data.txt', 'fastqc_report.html']
    ret_files = s3_utils.unzip_s3_to_s3(filename, prefix, retfile_list)
    assert 3 == len(ret_files.keys())
    assert ret_files['fastqc_report.html']['s3key'].startswith("https://s3.amazonaws.com")

    objs = s3_utils.s3_read_dir(prefix)
    assert objs.get('Contents', None)


@valid_env
@pytest.mark.webtest
def test_unzip_s3_to_s3_pairsqc(s3_utils):
    prefix = '__test_data/extracted'
    filename = '23d0a314-e401-4826-a76b-4356e019b059/report'
    s3_utils.s3_delete_dir(prefix)

    # ensure this thing was deleted
    # if no files there will be no Contents in response
    objs = s3_utils.s3_read_dir(prefix)
    assert [] == objs.get('Contents', [])

    # now copy to that dir we just deleted
    retfile_list = ['4DNFI1ZLO9D7.summary.out', 'pairsqc_report.html']
    ret_files = s3_utils.unzip_s3_to_s3(filename, prefix, retfile_list)
    return
    # TODO: fix this test
    assert 3 == len(ret_files.keys())
    assert ret_files['pairsqc_report.html']['s3key'].startswith("https://s3.amazonaws.com")

    objs = s3_utils.s3_read_dir(prefix)
    assert objs.get('Contents', None)


@valid_env
@pytest.mark.webtest
def test_create_sbg_workflow(sbg_project, sbg_keys):
    sbg = sbg_utils.SBGWorkflowRun(app_name='md5', token=sbg_keys, project_id=sbg_project)
    assert sbg.header
    assert sbg.header['X-SBG-Auth-Token'] == sbg_keys
    assert sbg.app_name == 'md5'


def test_create_sbg_workflow_from_event_parameter(workflow_event_data):
    wf = workflow_event_data['workflow']
    sbg = sbg_utils.create_sbg_workflow(**wf)
    assert sbg.export_id_list == wf['export_id_list']
    assert sbg.volume_list == wf['volume_list']
    assert sbg.import_id_list == wf['import_id_list']
    assert sbg.project_id == wf['project_id']
    assert sbg.app_name == wf['app_name']
    assert sbg.header == wf['header']
    assert sbg.task_input.__dict__ == wf['task_input']
    assert sbg.output_volume_id == wf['output_volume_id']


def test_create_workflowrun_from_event_parameter(ff_meta_event_data):
    meta = ff_meta_event_data['ff_meta'].copy()
    meta['app_name'] = 'md5'
    ff_wfr = ff_utils.WorkflowRunMetadata(**meta)
    assert ff_wfr


def test_tibanna():
    data = {'env': 'fourfront-webdev',
            'settings': {'1': '1'}}
    tibanna = Tibanna(**data)
    assert tibanna
    assert tibanna.as_dict() == data


def test_sbg_workflow_as_dict_clears_secrets(workflow_event_data):
    wf = workflow_event_data['workflow']
    sbg = sbg_utils.create_sbg_workflow(**wf)
    sbg_dict = sbg.as_dict()
    assert not sbg_dict.get('header')
    assert not sbg_dict.get('token')
    assert sbg_dict.get('output_volume_id') == wf['output_volume_id']


def test_ensure_list():
    assert ensure_list(5) == [5]
    assert ensure_list('hello') == ['hello']
    assert ensure_list(['hello']) == ['hello']
    assert ensure_list({'a': 'b'}) == [{'a': 'b'}]


# we need to use StillRunningException cause that's one of the special exceptions we don't
# catch in our powerup wrapper
@powerup("wrapped_fun", mock.Mock(side_effect=StillRunningException("metadata")))
def wrapped_fun(event, context):
    raise StillRunningException("I should not be called")


@powerup('error_fun', mock.Mock())
def error_fun(event, context):
    raise Exception("lambda made a mess")


def test_powerup_errors_are_dumped_into_return_dict():
    res = error_fun({'some': 'data'}, None)
    assert res['some'] == 'data'
    assert res['error'] == 'lambda made a mess'


def test_powerup_skips_when_appropriate():
    wrapped_fun({'skip': 'wrapped_fun'}, None)


def test_powerup_skips_in_list():
    wrapped_fun({'skip': ['wrapped_fun', 'fun2']}, None)


def test_powerup_normally_doesnt_skip():
    with pytest.raises(StillRunningException) as exec_nfo:
        wrapped_fun({'skip': 'somebody_else'}, None)
    assert exec_nfo
    assert 'should not be called' in str(exec_nfo.value)


def test_powerup_calls_metadata_only_func():
    with pytest.raises(StillRunningException) as exec_nfo:
        wrapped_fun({'skip': 'somebody_else', 'metadata_only': 'wrapped_fun'}, None)

    assert exec_nfo
    assert 'metadata' in str(exec_nfo.value)
