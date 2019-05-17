from tibanna_4dn.pony_utils import (
    TibannaSettings,
    WorkflowRunMetadata,
    ensure_list,
    Awsem,
    merge_source_experiments,
    ProcessedFileMetadata,
    FormatExtensionMap,
    get_extra_file_key,
    create_ffmeta_input_files_from_pony_input_file_list
)
import pytest
from tests.tibanna.pony.conftest import valid_env
from ..unicorn.test_utils import awsem_error_fun
from tibanna.utils import printlog
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
      },
      "push_error_to_end": True
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


def test_create_workflowrun_from_event_parameter(update_ffmeta_event_data_newmd5):
    meta = update_ffmeta_event_data_newmd5['ff_meta'].copy()
    meta['app_name'] = 'md5'
    ff_wfr = WorkflowRunMetadata(**meta)
    assert ff_wfr


def test_tibanna():
    data = {'env': 'fourfront-webdev',
            'settings': {'1': '1'}}
    tibanna = TibannaSettings(**data)
    assert tibanna
    assert tibanna.as_dict() == data


def test_ensure_list():
    assert ensure_list(5) == [5]
    assert ensure_list('hello') == ['hello']
    assert ensure_list(['hello']) == ['hello']
    assert ensure_list({'a': 'b'}) == [{'a': 'b'}]


def test_create_awsem(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    assert awsem.args
    assert awsem.config
    assert awsem.app_name
    assert awsem.output_s3
    assert awsem.output_files_meta


def test_get_output_files(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    of = awsem.output_files()
    assert 1 == len(of)
    assert of[0].runner == awsem
    assert of[0].bucket == awsem.output_s3
    assert of[0].key == 'lalala/md5_report'
    assert of[0].argument_type == 'Output report file'


def test_get_input_files(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    infiles = awsem.input_files()
    assert 1 == len(infiles)
    assert infiles[0].runner == awsem
    assert infiles[0].bucket == 'elasticbeanstalk-fourfront-webdev-files'
    assert infiles[0].key == 'f4864029-a8ad-4bb8-93e7-5108f462ccaa/4DNFIRSRJH45.fastq.gz'
    assert infiles[0].accession == '4DNFIRSRJH45'


def test_get_inputfile_accession(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    assert awsem.get_file_accessions('input_file')[0] == '4DNFIRSRJH45'


def test_get_inputfile_format_if_extra(update_ffmeta_event_data_extra_md5, tibanna_env):
    update_ffmeta_event_data_extra_md5.update(tibanna_env)
    for wf_file in Awsem(update_ffmeta_event_data_extra_md5).output_files():
        assert wf_file.runner.get_format_if_extras('input_file')[0] == 'pairs_px2'


@pytest.fixture()
def proc_file_in_webdev():
    return {'status': 'released',
            'uuid': 'f6d5ba22-aaf9-48e9-8df4-bc5c131c96af',
            'file_format': 'normvector_juicerformat',
            'accession': '4DNFIRO3UX7I',
            'award': '/awards/1U01CA200059-01/',
            'lab': '/labs/4dn-dcic-lab/'}


def test_create_ProcessedFileMetadata_from_get_error_if_no_at_type(ff_keys, proc_file_in_webdev):
    # can use acc, uuid, @id, any valid url
    with mock.patch('tibanna_4dn.pony_utils.get_metadata', return_value=proc_file_in_webdev):
        with pytest.raises(Exception) as expinfo:
            ProcessedFileMetadata.get(proc_file_in_webdev['accession'], ff_keys)
        assert "only load ProcessedFiles" in str(expinfo.value)


def test_create_ProcessedFileMetadata_from_get(ff_keys, proc_file_in_webdev):
    # can use acc, uuid, @id, any valid url
    file_with_type = proc_file_in_webdev.copy()
    file_with_type['@type'] = ['FileProcessed', 'Item', 'whatever']
    with mock.patch('tibanna_4dn.pony_utils.get_metadata', return_value=file_with_type) as ff:
        pf = ProcessedFileMetadata.get(proc_file_in_webdev['accession'], ff_keys)
        assert pf.__dict__ == proc_file_in_webdev
        assert type(pf) is ProcessedFileMetadata
        ff.was_called_once()


@valid_env
@pytest.mark.webtest
def test_format_extension_map(run_awsem_event_data):
    tibanna_settings = run_awsem_event_data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = TibannaSettings(env, ff_keys=run_awsem_event_data.get('ff_keys'),
                              settings=tibanna_settings)

    fe_map = FormatExtensionMap(tibanna.ff_keys)
    assert(fe_map)
    assert 'pairs' in fe_map.fe_dict.keys()


@valid_env
@pytest.mark.webtest
def test_merge_source_experiment(run_awsem_event_data):
    input_file = {
        "bucket_name": "elasticbeanstalk-fourfront-webdev-wfoutput",
        "workflow_argument_name": "input_pairs",
        "uuid": ["d2c897ec-bdb2-47ce-b1b1-845daccaa571", "d2c897ec-bdb2-47ce-b1b1-845daccaa571"],
        "object_key": ["4DNFI25JXLLI.pairs.gz", "4DNFI25JXLLI.pairs.gz"]
    }
    data = run_awsem_event_data
    tibanna_settings = data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = TibannaSettings(env, ff_keys=data.get('ff_keys'),
                              settings=tibanna_settings)
    res = merge_source_experiments(input_file['uuid'], tibanna.ff_keys, tibanna.env)
    printlog(res)
    assert 'fake_source_experiment' in res


@valid_env
@pytest.mark.webtest
def test_get_extra_file_key(run_awsem_event_data):
    tibanna_settings = run_awsem_event_data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = TibannaSettings(env, ff_keys=run_awsem_event_data.get('ff_keys'),
                              settings=tibanna_settings)
    fe_map = FormatExtensionMap(tibanna.ff_keys)
    infile_key = 'hahaha/lalala.bedGraph.gz'
    infile_format = 'bg'
    extra_file_format = 'bw'
    extra_file_key = get_extra_file_key(infile_format, infile_key, extra_file_format, fe_map)
    assert extra_file_key == 'hahaha/lalala.bw'


def test_powerup_add_awsem_error_to_output(ff_metadata):
    res = awsem_error_fun(ff_metadata, None)
    assert ('error' in res)


def test_create_ffmeta_input_files_from_pony_input_file_list():
    input_file_list = [{
          "bucket_name": "elasticbeanstalk-fourfront-webdev-wfoutput",
          "workflow_argument_name": "input_pairs1",
          "uuid": [['a', 'b'], ['c', 'd']],
          "object_key": [['e', 'f'], ['g', 'h']]
       },
       {
          "bucket_name": "elasticbeanstalk-fourfront-webdev-wfoutput",
          "workflow_argument_name": "input_pairs2",
          "uuid": ["d2c897ec-bdb2-47ce-b1b1-845daccaa571", "d2c897ec-bdb2-47ce-b1b1-845daccaa571"],
          "object_key": ["4DNFI25JXLLI.pairs.gz", "4DNFI25JXLLI.pairs.gz"]
       }
    ]
    res = create_ffmeta_input_files_from_pony_input_file_list(input_file_list)
    assert len(res) == 6
    assert 'dimension' in res[0]
    assert res[0]['dimension'] == '0-0'
    assert 'dimension' in res[1]
    assert res[1]['dimension'] == '0-1'
    assert res[1]['ordinal'] == 2
    assert 'dimension' in res[4]
    assert res[4]['dimension'] == '0'
