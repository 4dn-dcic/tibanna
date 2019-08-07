import copy
import uuid
from dcicutils import ff_utils
from tibanna_4dn.pony_utils import (
    FourfrontUpdater,
    TibannaSettings,
    QCArgumentInfo,
    InputExtraArgumentInfo
)
import pytest
from tests.tibanna.pony.conftest import (
    valid_env,
    update_ffmeta_event_data_fastqc2
)
from tibanna.utils import printlog

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
        qc = QCArgumentInfo(**qcarginfo)
    assert exec_info
    assert 'QCArgument it not Output QC file' in str(exec_info)

def test_FourfrontUpdater(update_ffmeta_event_data_fastqc2):
    updater = FourfrontUpdater(**update_ffmeta_event_data_fastqc2)
    assert updater
    assert updater.ff_meta
    assert updater.postrunjson
    assert updater.ff_output_files

@valid_env
def test_post_patch(update_ffmeta_event_data_fastqc2):
    updater = FourfrontUpdater(**update_ffmeta_event_data_fastqc2)
    item = updater.create_qc_template()
    item_uuid = item['uuid']
    updater.update_post_items(item_uuid, item, 'quality_metric_fastqc')
    assert 'uuid' in updater.post_items['quality_metric_fastqc'][item_uuid]
    assert updater.post_items['quality_metric_fastqc'][item_uuid]['uuid'] == item_uuid
    updater.post_all()
    updater.update_patch_items(item_uuid, {'Per base sequence content': 'PASS'})
    updater.patch_all()
    res = ff_utils.get_metadata(item_uuid, key=updater.tibanna_settings.ff_keys)
    assert res['Per base sequence content'] == 'PASS'
    updater.update_patch_items(item_uuid, {'status': 'deleted'})
    updater.patch_all()
    res = ff_utils.get_metadata(item_uuid, key=updater.tibanna_settings.ff_keys)
    assert res['status'] == 'deleted'

@valid_env
def test_FourfrontUpdater2(update_ffmeta_event_data_fastqc2):
    updater = FourfrontUpdater(**update_ffmeta_event_data_fastqc2)
    assert updater.workflow
    assert 'arguments' in updater.workflow
    assert updater.workflow_qc_arguments
    assert 'input_fastq' in updater.workflow_qc_arguments
    assert updater.workflow_qc_arguments['input_fastq'][0].qc_type == 'quality_metric_fastqc'
    updater.update_qc()
    qc = updater.workflow_qc_arguments['input_fastq'][0]
    target_accession = updater.accessions('input_fastq')[0]
    assert qc.workflow_argument_name == 'report_zip'
    assert len(qc.qc_zipped_tables) == 2
    assert target_accession == '4DNFIRSRJH45'
    data = updater.unzip_qc_data(qc, updater.file_key('report_zip'), target_accession)
    print(data.keys())
    assert data['fastqc_data.txt']['data'].startswith('##FastQC')
    qc_schema = updater.qc_schema('quality_metric_fastqc')
    assert 'Per base sequence content' in qc_schema
    qc_json = updater.parse_qc_table([data['summary.txt']['data'], data['fastqc_data.txt']['data']], qc_schema)
    assert 'Per base sequence content' in qc_json
    assert updater.post_items
    assert len(updater.post_items['quality_metric_fastqc']) == 1
    uuid = list(updater.post_items['quality_metric_fastqc'].keys())[0]
    assert 'url' in updater.post_items['quality_metric_fastqc'][uuid]
    assert 'Per base sequence content' in updater.post_items['quality_metric_fastqc'][uuid]

@valid_env
def test_FourfrontUpdater3(update_ffmeta_event_data_bamcheck):
    updater = FourfrontUpdater(**update_ffmeta_event_data_bamcheck)
    assert updater.workflow
    assert 'arguments' in updater.workflow
    assert updater.workflow_qc_arguments
    assert 'output' in updater.workflow_qc_arguments
    assert updater.workflow_qc_arguments['output'][0].qc_type == 'quality_metric_bamcheck'
    updater.update_qc()
    qc = updater.workflow_qc_arguments['output'][0]
    target_accession = updater.accessions('output')[0]
    assert qc.workflow_argument_name == 'output-check'
    assert qc.qc_table 
    assert target_accession == '4DNFIWT3X5RU'
    assert updater.post_items
    assert len(updater.post_items['quality_metric_bamcheck']) == 1
    uuid = list(updater.post_items['quality_metric_bamcheck'].keys())[0]
    assert 'quickcheck' in updater.post_items['quality_metric_bamcheck'][uuid]

