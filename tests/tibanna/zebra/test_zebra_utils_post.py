from tibanna_ffcommon.portal_utils import (
    TibannaSettings,
    FormatExtensionMap,
)
from tibanna_cgap.zebra_utils import (
    FourfrontStarter,
    FourfrontUpdater,
    ProcessedFileMetadata,
)
import pytest
from dcicutils import ff_utils
from tests.tibanna.zebra.conftest import valid_env


@valid_env
def test_fourfront_starter(start_run_event_md5):
    starter = FourfrontStarter(**start_run_event_md5)
    assert starter
    assert 'arguments' in starter.inp.wf_meta
    assert len(starter.inp.wf_meta['arguments']) == 2
    assert starter.inp.wf_meta['arguments'][1]['argument_type'] == 'Output report file'
    starter.run()
    assert len(starter.output_argnames) == 1


@valid_env
def test_qclist_handling():
    data = {'ff_meta': {'workflow': 'cgap:workflow_bwa-mem_no_unzip-check_v10'},
            '_tibanna': {'env': 'fourfront-cgap', 'settings': {'1': '1'}}}
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
    new_pf = ProcessedFileMetadata(file_format='bam').as_dict()
    ff_utils.post_metadata(new_pf, 'FileProcessed',
                           key=updater.tibanna_settings.ff_keys)
    updater.patch_qc(new_pf['uuid'], new_qc_object['uuid'], 'quality_metric_bamcheck')
    assert new_pf['uuid'] in updater.patch_items
    assert updater.patch_items[new_pf['uuid']]['quality_metric'] == new_qc_object['uuid']
    ff_utils.delete_metadata(new_pf['uuid'], key=updater.tibanna_settings.ff_keys)

    # file w/ quality_metric object of same type
    new_pf = ProcessedFileMetadata(file_format='bam').as_dict()
    existing_qc_object = updater.create_qc_template()
    ff_utils.post_metadata(existing_qc_object, 'QualityMetricBamcheck',
                           key=updater.tibanna_settings.ff_keys)
    new_pf['quality_metric'] = existing_qc_object['uuid']
    ff_utils.post_metadata(new_pf, 'FileProcessed',
                           key=updater.tibanna_settings.ff_keys)
    updater.patch_qc(new_pf['uuid'], new_qc_object['uuid'], 'quality_metric_bamcheck')
    assert new_pf['uuid'] in updater.patch_items
    assert updater.patch_items[new_pf['uuid']]['quality_metric'] == new_qc_object['uuid']
    ff_utils.delete_metadata(new_pf['uuid'], key=updater.tibanna_settings.ff_keys)
    ff_utils.delete_metadata(existing_qc_object['uuid'], key=updater.tibanna_settings.ff_keys)

    # file w/ quality_metric object of different type
    new_pf = ProcessedFileMetadata(file_format='bam').as_dict()
    existing_qc_object = updater.create_qc_template()
    ff_utils.post_metadata(existing_qc_object, 'QualityMetricWgsBamqc',
                           key=updater.tibanna_settings.ff_keys)
    new_pf['quality_metric'] = existing_qc_object['uuid']
    ff_utils.post_metadata(new_pf, 'FileProcessed',
                           key=updater.tibanna_settings.ff_keys)
    updater.patch_qc(new_pf['uuid'], new_qc_object['uuid'], 'quality_metric_bamcheck')
    assert new_pf['uuid'] in updater.patch_items
    new_qc_uuid = updater.patch_items[new_pf['uuid']]['quality_metric']
    assert new_qc_uuid in updater.post_items['quality_metric_qclist']
    res = updater.post_items['quality_metric_qclist'][new_qc_uuid]
    assert 'qc_list' in res
    assert len(res['qc_list']) == 2
    assert res['qc_list'][0]['qc_type'] == 'quality_metric_wgs_bamqc'
    assert res['qc_list'][1]['qc_type'] == 'quality_metric_bamcheck'
    assert res['qc_list'][0]['value'] == existing_qc_object['uuid']
    assert res['qc_list'][1]['value'] == new_qc_object['uuid']
    ff_utils.delete_metadata(new_pf['uuid'], key=updater.tibanna_settings.ff_keys)
    ff_utils.delete_metadata(existing_qc_object['uuid'], key=updater.tibanna_settings.ff_keys)

    # file w/ qc list with only quality_metric object of different type
    new_pf = ProcessedFileMetadata(file_format='bam').as_dict()
    existing_qc_object = updater.create_qc_template()
    ff_utils.post_metadata(existing_qc_object, 'QualityMetricWgsBamqc',
                           key=updater.tibanna_settings.ff_keys)
    existing_qclist_object = updater.create_qc_template()
    existing_qclist_object['qc_list'] = [{'qc_type': 'quality_metric_wgs_bamqc',
                                          'value': existing_qc_object['uuid']}]
    ff_utils.post_metadata(existing_qclist_object,
                           'QualityMetricQclist', key=updater.tibanna_settings.ff_keys)
    new_pf['quality_metric'] = existing_qclist_object['uuid']
    ff_utils.post_metadata(new_pf, 'FileProcessed',
                           key=updater.tibanna_settings.ff_keys)
    updater.patch_qc(new_pf['uuid'], new_qc_object['uuid'], 'quality_metric_bamcheck')
    assert new_pf['uuid'] not in updater.patch_items
    assert existing_qclist_object['uuid'] in updater.patch_items
    assert 'qc_list' in updater.patch_items[existing_qclist_object['uuid']]
    assert len(updater.patch_items[existing_qclist_object['uuid']]['qc_list']) == 2
    res = updater.patch_items[existing_qclist_object['uuid']]
    assert res['qc_list'][0]['qc_type'] == 'quality_metric_wgs_bamqc'
    assert res['qc_list'][1]['qc_type'] == 'quality_metric_bamcheck'
    assert existing_qc_object['uuid'] in res['qc_list'][0]['value']
    assert new_qc_object['uuid'] in res['qc_list'][1]['value']
    ff_utils.delete_metadata(new_pf['uuid'], key=updater.tibanna_settings.ff_keys)
    ff_utils.delete_metadata(existing_qclist_object['uuid'], key=updater.tibanna_settings.ff_keys)
    ff_utils.delete_metadata(existing_qc_object['uuid'], key=updater.tibanna_settings.ff_keys)

    # file w/ qc list with only quality_metric object of same type
    new_pf = ProcessedFileMetadata(file_format='bam').as_dict()
    existing_qc_object = updater.create_qc_template()
    ff_utils.post_metadata(existing_qc_object, 'QualityMetricBamcheck',
                           key=updater.tibanna_settings.ff_keys)
    existing_qclist_object = updater.create_qc_template()
    existing_qclist_object['qc_list'] = [{'qc_type': 'quality_metric_bamcheck',
                                          'value': existing_qc_object['uuid']}]
    ff_utils.post_metadata(existing_qclist_object,
                           'QualityMetricQclist', key=updater.tibanna_settings.ff_keys)
    new_pf['quality_metric'] = existing_qclist_object['uuid']
    ff_utils.post_metadata(new_pf, 'FileProcessed',
                           key=updater.tibanna_settings.ff_keys)
    updater.patch_qc(new_pf['uuid'], new_qc_object['uuid'], 'quality_metric_bamcheck')
    assert new_pf['uuid'] not in updater.patch_items
    assert existing_qclist_object['uuid'] in updater.patch_items
    assert 'qc_list' in updater.patch_items[existing_qclist_object['uuid']]
    assert len(updater.patch_items[existing_qclist_object['uuid']]['qc_list']) == 1
    res = updater.patch_items[existing_qclist_object['uuid']]
    assert res['qc_list'][0]['qc_type'] == 'quality_metric_bamcheck'
    assert res['qc_list'][0]['value'] == new_qc_object['uuid']
    ff_utils.delete_metadata(new_pf['uuid'], key=updater.tibanna_settings.ff_keys)
    ff_utils.delete_metadata(existing_qclist_object['uuid'], key=updater.tibanna_settings.ff_keys)
    ff_utils.delete_metadata(existing_qc_object['uuid'], key=updater.tibanna_settings.ff_keys)

