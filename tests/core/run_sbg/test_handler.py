import pytest
from core.run_sbg import service
from core import utils


@pytest.fixture
def md5_event_data():
    return {
      "input_files": [
        {
          "bucket_name": "encoded-4dn-files",
          "object_key": "4DNFI067AFHV.fastq.gz",
          "uuid": "46e82a90-49e5-4c33-afab-9ec90d65cca1",
          "workflow_argument_name": "input_file"
        }
      ],
      "app_name": "md5",
      "workflow_uuid": "d3f25cd3-e726-4b3c-a022-48f844474b41",
      "parameters": {}
    }


@pytest.fixture
def multi_infile_data():
    return {
      "input_files": [
        {
          "bucket_name": "encoded-4dn-files",
          "object_key": "4DNFI067AFHV.fastq.gz",
          "uuid": "46e82a90-49e5-4c33-afab-9ec90d65cca1",
          "workflow_argument_name": "input_file"
        },
        {
          "bucket_name": "encoded-4dn-files",
          "object_key": "4DNFI9MA6LRV.fastq.gz",
          "uuid": "0626affd-5208-48a0-9081-9e03475fbeaa",
          "workflow_argument_name": "input_file"
        }

      ],
      "app_name": "md5",
      "workflow_uuid": "d3f25cd3-e726-4b3c-a022-48f844474b41",
      "parameters": {}
    }


@pytest.mark.webtest
@pytest.fixture
def md5_sbg_wfrun():
    return service.create_sbg_workflow('md5')


@pytest.mark.webtest
def test_mount_on_sbg(md5_event_data, md5_sbg_wfrun):
    s3_key = utils.get_s3_keys()
    input_file = md5_event_data['input_files'][0]
    assert service.mount_on_sbg(input_file, s3_key, md5_sbg_wfrun)


@pytest.mark.webtest
def test_mount_multiple_on_sbg(md5_sbg_wfrun, multi_infile_data):
    s3_key = utils.get_s3_keys()
    input_file_list = multi_infile_data['input_files']
    mounts3_tasks = [service.mount_on_sbg(infile, s3_key, md5_sbg_wfrun)
                     for infile in input_file_list]
    assert len(mounts3_tasks) == 2


@pytest.mark.webtest
def test_handler(md5_event_data):
    return
    service.handler(md5_event_data, '')
