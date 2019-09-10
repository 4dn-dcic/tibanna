import copy
from tibanna_ffcommon.portal_utils import (
    TibannaSettings,
    ensure_list,
    FFInputAbstract,
    WorkflowRunMetadataAbstract,
    FourfrontStarterAbstract,
    ProcessedFileMetadataAbstract,
    QCArgumentInfo,
)
from tibanna_ffcommon.exceptions import (
    MalFormattedFFInputException
)
import pytest
from tibanna.utils import printlog
import mock


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


def test_ff_input_abstract():
    data = {'workflow_uuid': 'a',
            'config': {'log_bucket': 'b'},
            'output_bucket': 'c'}
    inp = FFInputAbstract(**data)
    assert inp.workflow_uuid == 'a'
    assert inp.config.log_bucket == 'b'


def test_ff_input_abstract_missing_field_error():
    data = {'workflow_uuid': 'a',
            'config': {'log_bucket': 'b'}}
    with pytest.raises(MalFormattedFFInputException) as excinfo:
        FFInputAbstract(**data)
    assert "missing field in input json: output_bucket" in str(excinfo)


def test_ff_input_abstract_missing_field_error2():
    data = {'workflow_uuid': 'a',
            'output_bucket': 'c'}
    with pytest.raises(MalFormattedFFInputException) as excinfo:
        FFInputAbstract(**data)
    assert "missing field in input json: config" in str(excinfo)


def test_ff_input_abstract_missing_field_error3():
    data = {'config': {'log_bucket': 'b'},
            'output_bucket': 'c'}
    with pytest.raises(MalFormattedFFInputException) as excinfo:
        FFInputAbstract(**data)
    assert "missing field in input json: workflow_uuid" in str(excinfo)


def test_workflow_run_metadata_abstract():
    data = {'workflow': 'a', 'awsem_app_name': 'b', 'app_version': 'c'}
    ff = WorkflowRunMetadataAbstract(**data)
    assert ff.workflow == 'a'
    assert ff.awsem_app_name == 'b'
    assert ff.title.startswith('b c run')


def test_workflow_run_metadata_abstract_missing_field_error1():
    data = {'awsem_app_name': 'b', 'app_version': 'c'}
    with pytest.raises(Exception) as excinfo:
        WorkflowRunMetadataAbstract(**data)
    assert 'missing' in str(excinfo)


def test_workflow_run_metadata_abstract_missing_field_error2():
    data = {'workflow': 'a', 'app_version': 'c'}
    with pytest.raises(Exception) as excinfo:
        WorkflowRunMetadataAbstract(**data)
    assert 'missing' in str(excinfo)


def test_processed_file_metadata_abstract():
    data = {'uuid': 'a'}
    pf = ProcessedFileMetadataAbstract(**data)
    assert pf.uuid == 'a'


def test_create_ff_input_files():
    input_file_list = [{
          "bucket_name": "bucket1",
          "workflow_argument_name": "input_pairs1",
          "uuid": [['a', 'b'], ['c', 'd']],
          "object_key": [['e', 'f'], ['g', 'h']]
       },
       {
          "bucket_name": "bucket1",
          "workflow_argument_name": "input_pairs2",
          "uuid": ["d2c897ec-bdb2-47ce-b1b1-845daccaa571", "d2c897ec-bdb2-47ce-b1b1-845daccaa571"],
          "object_key": ["4DNFI25JXLLI.pairs.gz", "4DNFI25JXLLI.pairs.gz"]
       }
    ]
    starter = FourfrontStarterAbstract(input_files=input_file_list,
                                       workflow_uuid='a',
                                       config={'log_bucket': 'b'},
                                       output_bucket='c')
    res = starter.create_ff_input_files()
    assert len(res) == 6
    assert 'dimension' in res[0]
    assert res[0]['dimension'] == '0-0'
    assert 'dimension' in res[1]
    assert res[1]['dimension'] == '0-1'
    assert res[1]['ordinal'] == 2
    assert 'dimension' in res[4]
    assert res[4]['dimension'] == '0'


@pytest.fixture
def qcarginfo_fastqc():
    return {
        "argument_type": "Output QC file",
        "workflow_argument_name": "report_zip",
        "argument_to_be_attached_to": "input_fastq",
        "qc_zipped": True,
        "qc_html": True,
        "qc_json": False,
        "qc_table": True,
        "qc_zipped_html": "fastqc_report.html",
        "qc_zipped_tables": ["summary.txt", "fastqc_data.txt"],
        "qc_type": "quality_metric_fastqc"
    }


def test_QCArgumentInfo(qcarginfo_fastqc):
    qc = QCArgumentInfo(**qcarginfo_fastqc)
    assert qc.qc_zipped
    assert qc.qc_html
    assert qc.qc_table
    assert qc.qc_type == "quality_metric_fastqc"


def test_wrong_QCArgumentInfo(qcarginfo_fastqc):
    qcarginfo = copy.deepcopy(qcarginfo_fastqc)
    qcarginfo['argument_type'] = 'Output processed file'
    with pytest.raises(Exception) as exec_info:
        QCArgumentInfo(**qcarginfo)
    assert exec_info
    assert 'QCArgument it not Output QC file' in str(exec_info)
