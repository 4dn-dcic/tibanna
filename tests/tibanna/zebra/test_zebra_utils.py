from tibanna_ffcommon.portal_utils import (
    TibannaSettings,
    FormatExtensionMap,
)
from tibanna_cgap.zebra_utils import (
    WorkflowRunMetadata,
    ProcessedFileMetadata,
    FourfrontStarter
)
import pytest
from tests.tibanna.zebra.conftest import valid_env
from tibanna.utils import printlog


@valid_env
def test_tibanna():
    data = {'env': 'fourfront-cgap',
            'settings': {'1': '1'}}
    tibanna = TibannaSettings(**data)
    assert tibanna
    assert tibanna.as_dict() == data


@valid_env
def test_format_extension_map():
    data = {'env': 'fourfront-cgap',
            'settings': {'1': '1'}}
    tibanna = TibannaSettings(**data)
    fe_map = FormatExtensionMap(tibanna.ff_keys)
    assert(fe_map)
    assert 'bwt' in fe_map.fe_dict.keys()


@valid_env
def test_fourfront_starter2(start_run_event_bwa_check):
    starter = FourfrontStarter(**start_run_event_bwa_check)
    assert starter
    assert not starter.user_supplied_output_files('raw_bam')
    assert len(starter.output_argnames) == 2
    assert starter.output_argnames[0] == 'raw_bam'
    assert starter.arg('raw_bam')['argument_type'] == 'Output processed file'
    assert starter.pf('raw_bam')
    starter.create_pfs()
    assert len(starter.pfs) == 1


@valid_env
def test_fastqc():
    data = {'workflow': '4dn-dcic-lab:workflow_bwa-mem_no_unzip-check_v9',
            '_tibanna': {'env': 'fourfront-cgap', 'settings': {'1': '1'}}
    updater = FourfrontUpdater(**data)
    assert updater
    assert updater.workflow_qc_arguments
    assert updater.workflow
    assert 'arguments' in updater.workflow
    assert updater.workflow_qc_arguments
    assert 'raw_bam' in updater.workflow_qc_arguments
    assert updater.workflow_qc_arguments['raw_bam'][0].qc_type == 'quality_metric_bamcheck'
    new_qc_object = updater.create_qc_template()

    # file w/ no quality_metric object
    new_pf = ProcessedMetadata().as_dict()
    ff_utils.post_metadata(new_pf, new_pf['uuid'], 'FileProcessed', key=tibanna.ff_keys)
    updater.patch_qc(new_pf['uuid'], new_qc_object['uuid'], 'quality_metric_bamcheck')
    assert new_pf['uuid'] in updater.patch_items
    assert updater.patch_items[new_pf['uuid']]['quality_metric'] == new_qc_object['uuid']
    ff_utils.delete_metadata(new_pf['uuid'], key=updater.tibanna_settings.ff_keys)

    # file w/ quality_metric object of same type
    new_pf = ProcessedMetadata().as_dict()
    existing_qc_object = updater.create_qc_template()
    ff_utils.post_metadata(existing_qc_object, existing_qc_object['uuid'], 'QualityMetricBamcheck',
                           key=updater.tibanna_settings.ff_keys)
    new_pf['quality_metric'] = existing_qc_object['uuid']
    ff_utils.post_metadata(new_pf, new_pf['uuid'], 'FileProcessed',
                           key=updater.tibanna_settings.ff_keys)
    updater.patch_qc(new_pf['uuid'], new_qc_object['uuid'], 'quality_metric_bamcheck')
    assert new_pf['uuid'] in updater.patch_items
    assert updater.patch_items[new_pf['uuid']]['quality_metric'] == new_qc_object['uuid']
    ff_utils.delete_metadata(existing_qc_object['uuid'], key=updater.tibanna_settings.ff_keys)
    ff_utils.delete_metadata(new_pf['uuid'], key=updater.tibanna_settings.ff_keys)

    # file w/ quality_metric object of different type
    new_pf = ProcessedMetadata().as_dict()
    existing_qc_object = updater.create_qc_template()
    ff_utils.post_metadata(existing_qc_object, existing_qc_object['uuid'], 'QualityMetricWgsBamqc',
                           key=updater.tibanna_settings.ff_keys)
    new_pf['quality_metric'] = existing_qc_object['uuid']
    ff_utils.post_metadata(new_pf, new_pf['uuid'], 'FileProcessed',
                           key=updater.tibanna_settings.ff_keys)
    updater.patch_qc(new_pf['uuid'], new_qc_object['uuid'], 'quality_metric_bamcheck')
    assert new_pf['uuid'] in updater.patch_items
    new_qc_uuid = updater.patch_items[new_pf['uuid']]['quality_metric']
    assert new_qc_uuid in updater.post_items
    res = updater.post_items[new_qc_uuid]
    assert 'qc_list' in res
    assert len(res['qc_list']) == 2
    assert res['qc_list'][0]['qc_type'] == 'quality_metric_wgs_bamqc'
    assert res['qc_list'][1]['qc_type'] == 'quality_metric_bamcheck'
    assert res['qc_list'][0]['value'] == existing_qc_object['uuid']
    assert res['qc_list'][1]['value'] == new_qc_object['uuid']
    ff_utils.delete_metadata(existing_qc_object['uuid'], key=updater.tibanna_settings.ff_keys)
    ff_utils.delete_metadata(new_pf['uuid'], key=updater.tibanna_settings.ff_keys)

    # file w/ qc list with only quality_metric object of different type
    new_pf = ProcessedMetadata().as_dict()
    existing_qc_object = updater.create_qc_template()
    ff_utils.post_metadata(existing_qc_object, existing_qc_object['uuid'], 'QualityMetricWgsBamqc',
                           key=updater.tibanna_settings.ff_keys)
    existing_qclist_object = updater.create_qc_template()
    


