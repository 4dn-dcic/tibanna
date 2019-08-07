import copy
import uuid
import boto3
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


def test_postrunjson_link(update_ffmeta_event_data_repliseq):
    updater = FourfrontUpdater(**update_ffmeta_event_data_repliseq)
    assert updater.ff_meta.awsem_postrun_json == 'https://s3.amazonaws.com/tibanna-output/Gkx8WiCOHJPq.postrun.json'


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
def test_md5(update_ffmeta_event_data_newmd5):
    report_key = 'lalala/md5_report'
    s3 = boto3.client('s3')
    s3.put_object(Body='1234\n5678'.encode('utf-8'),
                  Bucket='tibanna-output', Key=report_key)
    updater = FourfrontUpdater(**update_ffmeta_event_data_newmd5)
    with pytest.raises(Exception) as exec_info:
        updater.update_md5()
    assert 'md5 not matching the original one' in str(exec_info)
    real_md5_content = 'bc75002f8a473bc6854d562789525a90\n6bb2dfa5b435ed03105cb59c32442d23'
    s3.put_object(Body=real_md5_content.encode('utf-8'),
                  Bucket='tibanna-output', Key=report_key)
    updater.update_md5()
    md5, content_md5 = updater.parse_md5_report(updater.read('report'))
    assert md5 == 'bc75002f8a473bc6854d562789525a90'
    assert content_md5 == '6bb2dfa5b435ed03105cb59c32442d23'
    assert 'f4864029-a8ad-4bb8-93e7-5108f462ccaa' in updater.patch_items
    assert 'md5sum' not in updater.patch_items['f4864029-a8ad-4bb8-93e7-5108f462ccaa'] # already in
    assert 'file_size' in updater.patch_items['f4864029-a8ad-4bb8-93e7-5108f462ccaa']
    assert 'status' in updater.patch_items['f4864029-a8ad-4bb8-93e7-5108f462ccaa']
    

@valid_env
def test_md5_for_extra(update_ffmeta_event_data_extra_md5):
    updater = FourfrontUpdater(**update_ffmeta_event_data_extra_md5)
    assert updater.input_argnames[0] == 'input_file'
    assert 'format_if_extra' in updater.ff_file('input_file')
    format_if_extras = updater.format_if_extras(updater.input_argnames[0])
    assert len(format_if_extras) == 1
    assert format_if_extras[0] == 'pairs_px2'
    updater.update_md5()
    assert updater.bucket('report') == 'elasticbeanstalk-fourfront-webdev-wfoutput'
    assert updater.file_key('report') == 'f1340bec-a842-402c-bbac-6e239df96682/report822085265412'
    assert updater.status('report') == 'COMPLETED'
    assert '12005967-f060-40dd-a63c-c7204dcf46a7' in updater.patch_items


@valid_env
def test_input_extra(update_ffmeta_event_data_bed2multivec):
    updater = FourfrontUpdater(**update_ffmeta_event_data_bed2multivec)
    assert 'bedfile' in updater.workflow_input_extra_arguments
    assert len(updater.workflow_input_extra_arguments['bedfile']) == 1
    ie = updater.workflow_input_extra_arguments['bedfile'][0]
    assert ie.workflow_argument_name == 'multivec_file'
    updater.update_input_extras()
    assert 'ff6df769-40f3-486f-a46a-872de0828905' in updater.patch_items
    assert 'extra_files' in updater.patch_items['ff6df769-40f3-486f-a46a-872de0828905']
    extra = updater.patch_items['ff6df769-40f3-486f-a46a-872de0828905']['extra_files'][0]
    assert extra['md5sum'] == '076ea000a803357f2a88f725ffeff435'
    assert extra['file_size'] == 8688344
    assert extra['status'] == 'uploaded'


@valid_env
def test_pf(update_ffmeta_hicbam):
    updater = FourfrontUpdater(**update_ffmeta_hicbam)
    updater.update_all_pfs()
    assert updater.patch_items
    assert 'eacc2a43-9fe8-41a7-89f4-7093619fde31' in updater.patch_items
    assert '5bded0bb-e429-48a2-bb85-e558111924e7' in updater.patch_items
    assert 'md5sum' in updater.patch_items['eacc2a43-9fe8-41a7-89f4-7093619fde31']
    assert 'file_size' in updater.patch_items['eacc2a43-9fe8-41a7-89f4-7093619fde31']
    assert 'status' in updater.patch_items['eacc2a43-9fe8-41a7-89f4-7093619fde31']
    outbam_patch = updater.patch_items['eacc2a43-9fe8-41a7-89f4-7093619fde31']
    assert outbam_patch['md5sum'] == 'eeff1f1bad00c0b386a3ce5f5751e1cc'
    assert outbam_patch['file_size'] == 313108291
    assert outbam_patch['status'] == 'uploaded'
    outpairs_patch = updater.patch_items['5bded0bb-e429-48a2-bb85-e558111924e7']
    assert outpairs_patch['extra_files'][0]['md5sum'] == '82ae753a21a52886d1e303c525208332'
    assert outpairs_patch['extra_files'][0]['file_size'] == 3300298
    assert outpairs_patch['extra_files'][0]['status'] == 'uploaded'


@valid_env
def test_fastqc(update_ffmeta_event_data_fastqc2):
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
def test_bamcheck(update_ffmeta_event_data_bamcheck):
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


@valid_env
def test_pairsqc(update_ffmeta_event_data_pairsqc):
    updater = FourfrontUpdater(**update_ffmeta_event_data_pairsqc)
    updater.update_qc()
    qc = updater.workflow_qc_arguments['input_pairs'][0]
    assert qc.workflow_argument_name == 'report'
    target_accession = updater.accessions('input_pairs')[0]
    assert target_accession == '4DNFI1ZLO9D7'
    assert updater.post_items
    assert len(updater.post_items['quality_metric_pairsqc']) == 1
    uuid = list(updater.post_items['quality_metric_pairsqc'].keys())[0]
    assert 'Cis/Trans ratio' in updater.post_items['quality_metric_pairsqc'][uuid]


@valid_env
def test_repliseq(update_ffmeta_event_data_repliseq):
    updater = FourfrontUpdater(**update_ffmeta_event_data_repliseq)
    updater.update_all_pfs()
    updater.update_qc()
    qc = updater.workflow_qc_arguments['filtered_sorted_deduped_bam'][0]
    target_accession = updater.accessions('filtered_sorted_deduped_bam')[0]
    assert target_accession == '4DNFIP2T7ANW'
    assert updater.post_items
    assert len(updater.post_items['quality_metric_dedupqc_repliseq']) == 1
    uuid = list(updater.post_items['quality_metric_dedupqc_repliseq'].keys())[0]
    assert 'Proportion of removed duplicates' in updater.post_items['quality_metric_dedupqc_repliseq'][uuid]
    assert updater.patch_items
    assert '050c9382-61d7-49e8-8598-1a6734dda5d2' in updater.patch_items
    bam_patch = updater.patch_items['050c9382-61d7-49e8-8598-1a6734dda5d2']  # filtered bam
    assert 'md5sum' in bam_patch
    assert 'file_size' in bam_patch
    assert 'status' in bam_patch
    assert bam_patch['md5sum'] == '908488c3d8bea2875551c67c9fd1b3dc'
    assert bam_patch['file_size'] == 11061946
    assert bam_patch['status'] == 'uploaded'
    assert 'quality_metric' in updater.patch_items['4DNFIP2T7ANW'] # qc_metric is patched by accession
    assert '4127ad92-16cf-4716-ab68-dc9b352658eb' in updater.patch_items
    bg_patch = updater.patch_items['4127ad92-16cf-4716-ab68-dc9b352658eb']  # count_bg
    assert 'extra_files' in bg_patch
    assert len(bg_patch['extra_files']) == 2
    assert bg_patch['extra_files'][1]['file_format'] == 'bw'
    assert bg_patch['extra_files'][1]['md5sum'] == 'f08575a366c14dbc949d35e415151cfd'
    assert bg_patch['extra_files'][1]['file_size'] == 3120059
    assert bg_patch['extra_files'][1]['status'] == 'uploaded'
    assert bg_patch['extra_files'][0]['file_format'] == 'bg_px2'
    assert bg_patch['extra_files'][0]['md5sum'] == 'aa8e2848e1f022b197fe31c804de08bf'
    assert bg_patch['extra_files'][0]['file_size'] == 991610
    assert bg_patch['extra_files'][0]['status'] == 'uploaded'
