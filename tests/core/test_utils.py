from core.utils import (
    Tibanna,
    powerup,
    StillRunningException,
    AWSEMJobErrorException,
    WorkflowRunMetadata,
    ensure_list,

)
import pytest
from conftest import valid_env
import mock


@pytest.fixture
def ff_metadata():
    return {
      "app_name": "md5",
      "_tibanna": {
        "env": "fourfront-webprod",
        "settings": {
          "url": "",
          "run_type": "md5",
          "run_name": "md5_4DNFIIE1QWPL.fastq.gz",
          "env": "fourfront-webprod",
          "run_id": "4DNFIIE1QWPL.fastq.gz"
        }
      },
      "ff_meta": {
        "run_platform": "AWSEM",
        "uuid": "71d4d068-1b17-4e99-8b59-cfc561266b45",
        "parameters": [],
        "workflow": "d3f25cd3-e726-4b3c-a022-48f844474b41",
        "title": "md5 run 2018-02-06 21:41:42.750987",
        "award": "1U01CA200059-01",
        "awsem_job_id": "",
        "awsem_app_name": "md5",
        "lab": "4dn-dcic-lab",
        "run_status": "started",
        "output_files": [
          {
            "type": "Output report file",
            "workflow_argument_name": "report"
          }
        ],
        "input_files": [
          {
            "ordinal": 1,
            "workflow_argument_name": "input_file",
            "value": "b4f6807c-6f93-4b7d-91ff-ff95e801165c"
          }
        ]
      }
    }


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


def test_create_workflowrun_from_event_parameter(update_ffmeta_event_data_newmd5):
    meta = update_ffmeta_event_data_newmd5['ff_meta'].copy()
    meta['app_name'] = 'md5'
    ff_wfr = WorkflowRunMetadata(**meta)
    assert ff_wfr


def test_tibanna():
    data = {'env': 'fourfront-webdev',
            'settings': {'1': '1'}}
    tibanna = Tibanna(**data)
    assert tibanna
    assert tibanna.as_dict() == data


def test_ensure_list():
    assert ensure_list(5) == [5]
    assert ensure_list('hello') == ['hello']
    assert ensure_list(['hello']) == ['hello']
    assert ensure_list({'a': 'b'}) == [{'a': 'b'}]


@powerup("wrapped_fun", mock.Mock(side_effect=StillRunningException("metadata")))
def wrapped_fun(event, context):
    raise StillRunningException("I should not be called")


# this will raise an error
@powerup("update_ffmeta_awsem", mock.Mock())
def update_ffmeta_error_fun(event, context):
    raise Exception("I should raise an error")


@powerup('error_fun', mock.Mock())
def error_fun(event, context):
    raise Exception("lambda made a mess")


@powerup('awsem_error_fun', mock.Mock())
def awsem_error_fun(event, context):
    raise AWSEMJobErrorException()


def test_powerup_errors_are_dumped_into_return_dict():
    res = error_fun({'some': 'data'}, None)
    assert res['some'] == 'data'
    assert res['error']
    assert 'Error on step: error_fun' in res['error']


def test_powerup_throws_if_error_set_in_input_json():
    # only throw the error because lambda name is update_ffmeta_awsem
    with pytest.raises(Exception):
        update_ffmeta_error_fun({'error': 'same like skip'}, None)


def test_powerup_error_thrown_if_ignored_exceptions():
    # throw an error because this is an ignored exception and
    # no 'error' in event json
    with pytest.raises(Exception):
        wrapped_fun({}, None)


def test_powerup_error_propogates():
    # skip throwing an error because 'error' is in event json and the
    # lambda name != update_ffmeta_awsem. error is propagated to the res
    # and will be returned exactly as input
    res = wrapped_fun({'error': 'should not raise'}, None)
    assert res['error'] == 'should not raise'


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


def test_powerup_add_awsem_error_to_output(ff_metadata):
    res = awsem_error_fun(ff_metadata, None)
    assert ('error' in res)
