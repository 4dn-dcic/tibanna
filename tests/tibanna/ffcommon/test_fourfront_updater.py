import copy
from tibanna_ffcommon.portal_utils import (
    QCArgumentInfo,
)
import pytest

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

