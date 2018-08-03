import pytest
from core.start_run_awsem.service import (
    handler,
    handle_processed_files,
    proc_file_for_arg_name,
    process_input_file_info,
    add_secondary_files_to_args,
)
from ..conftest import valid_env
from core.pony_utils import Tibanna, ProcessedFileMetadata
from dcicutils import ff_utils
import mock


@valid_env
@pytest.mark.webtest
def test_start_awsem_handler(run_awsem_event_data):
    with mock.patch('core.pony_utils.post_metadata') as mock_request:
        res = handler(run_awsem_event_data, '')
        assert mock_request.call_count == 1  # one for wfr, no pf
    assert(res)
    assert 'ff_meta' in res
    assert 'notes' in res['ff_meta']
    assert 'award' in res['ff_meta']
    assert res['ff_meta']['award'] == '/awards/1U01DA040582-01/'


@valid_env
@pytest.mark.webtest
def test_start_awsem_handler_processed_files(run_awsem_event_data_processed_files):
    with mock.patch('core.pony_utils.post_metadata') as mock_request:
        res = handler(run_awsem_event_data_processed_files, '')
        assert mock_request.call_count == 2  # one for wfr, two pfs.
    assert(res)
    assert('pf_meta' in res)
    assert('genome_assembly' in res['pf_meta'][0])
    assert(res['pf_meta'][0]['genome_assembly'] == 'GRCh38')


@pytest.fixture()
def proc_file_in_webdev():
    return {'status': 'released',
            'uuid': 'f6d5ba22-aaf9-48e9-8df4-bc5c131c96af',
            'file_format': 'normvector_juicerformat',
            'accession': '4DNFIRO3UX7I',
            'award': '/awards/1U01CA200059-01/',
            'lab': '/labs/4dn-dcic-lab/'}


@valid_env
@pytest.mark.webtest
def test_proc_file_for_arg_name(run_awsem_event_data_processed_files, proc_file_in_webdev):
    of = [{"workflow_argument_name": "output_file1",
           "uuid": proc_file_in_webdev['uuid']
           },
          {"workflow_argument_name": "output_file2",
           "uuid": "f4864029-a8ad-4bb8-93e7-5108f46bbbbb"
           }]

    tibanna_settings = run_awsem_event_data_processed_files.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, ff_keys=run_awsem_event_data_processed_files.get('ff_keys'),
                      settings=tibanna_settings)

    file_with_type = proc_file_in_webdev.copy()
    file_with_type['@type'] = ['FileProcessed', 'Item', 'whatever']
    with mock.patch('core.pony_utils.get_metadata', return_value=file_with_type):
        pf, resp = proc_file_for_arg_name(of, 'output_file1', tibanna)
        assert type(pf) == ProcessedFileMetadata
        assert pf.__dict__ == proc_file_in_webdev


@pytest.mark.webtest
def test_pseudo_run(run_task_awsem_pseudo_workflow_event_data):
    with mock.patch('core.pony_utils.post_metadata') as mock_request:
        res = handler(run_task_awsem_pseudo_workflow_event_data, '')
        mock_request.assert_called_once()
    assert(res)
    # check pf_meta
    user_supplied_of = [of['uuid'] for of in
                        run_task_awsem_pseudo_workflow_event_data['output_files']]

    for pf in res['pf_meta']:
        assert pf['uuid'] in user_supplied_of

    for of in res['ff_meta']['output_files']:
        assert of['value'] in user_supplied_of


@pytest.mark.webtest
def test_pseudo_run_add_extra_meta(run_task_awsem_pseudo_workflow_event_data):
    wfr_meta = {'description': 'test-descrip',
                'awsem_job_id': 'test-pseudo-run',
                }

    run_task_awsem_pseudo_workflow_event_data['wfr_meta'] = wfr_meta
    with mock.patch('core.pony_utils.post_metadata') as mock_request:
        res = handler(run_task_awsem_pseudo_workflow_event_data, '')
        mock_request.assert_called_once()
    assert(res)

    # did we set additional fields correctly
    for k, v in wfr_meta.iteritems():
        assert res['ff_meta'][k] == v

    # just to be extra safe, also check pfmeta
    user_supplied_of = [of['uuid'] for of in
                        run_task_awsem_pseudo_workflow_event_data['output_files']]

    for pf in res['pf_meta']:
        assert pf['uuid'] in user_supplied_of

    for of in res['ff_meta']['output_files']:
        assert of['value'] in user_supplied_of


@valid_env
@pytest.mark.webtest
def test_start_awsem_handle_processed_files2(run_awsem_event_data_processed_files2):
    with mock.patch('core.pony_utils.post_metadata') as mock_request:
        res = handler(run_awsem_event_data_processed_files2, '')
        assert mock_request.call_count == 3  # one for wfr, two pfs.
    assert(res)
    assert('pf_meta' in res)
    assert('source_experiments' in res['pf_meta'][0])
    assert('genome_assembly' in res['pf_meta'][0])
    assert(res['pf_meta'][0]['genome_assembly'] == 'GRCh38')
    assert('genome_assembly' in res['pf_meta'][1])
    assert(res['pf_meta'][1]['genome_assembly'] == 'GRCh38')


@valid_env
@pytest.mark.webtest
def test_handle_processed_files(run_awsem_event_data_secondary_files):
    data = run_awsem_event_data_secondary_files
    tibanna_settings = data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, ff_keys=data.get('ff_keys'),
                      settings=tibanna_settings)
    workflow_uuid = data['workflow_uuid']
    workflow_info = ff_utils.get_metadata(workflow_uuid, key=tibanna.ff_keys)

    with mock.patch('core.pony_utils.post_metadata') as mock_request:
        output_files, pf_meta = handle_processed_files(workflow_info, tibanna)
        assert mock_request.call_count == 3
    assert(output_files)
    assert len(output_files) == 3
    for of in output_files:
        if of['extension'] == '.pairs.gz':
            assert of['secondary_file_extensions'] == ['.pairs.gz.px2']
            assert of['secondary_file_formats'] == ['pairs_px2']
            assert of['extra_files']
        else:
            assert 'secondary_files_extension' not in of
            assert 'secondary_files_formats' not in of

    assert(pf_meta)
    assert len(pf_meta) == 3
    for pf in pf_meta:
        pdict = pf.__dict__
        if pdict['file_format'] == 'pairs':
            assert pdict['extra_files'] == [{'file_format': 'pairs_px2'}]
        else:
            assert 'extra_files' not in pdict


@valid_env
@pytest.mark.webtest
def test_handle_processed_files2(run_awsem_event_data_processed_files2):
    data = run_awsem_event_data_processed_files2
    tibanna_settings = data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, ff_keys=data.get('ff_keys'),
                      settings=tibanna_settings)
    workflow_uuid = data['workflow_uuid']
    workflow_info = ff_utils.get_metadata(workflow_uuid, key=tibanna.ff_keys)

    output_files, pf_meta = handle_processed_files(workflow_info, tibanna,
                                                   custom_fields=data.get('custom_pf_fields'))
    assert(pf_meta)
    assert(output_files)
    for pf in pf_meta:
        pdict = pf.__dict__
        assert 'genome_assembly' in pdict
        assert pdict['genome_assembly'] == 'GRCh38'


@valid_env
@pytest.mark.webtest
def test_process_input_file_info(run_awsem_event_data):
    input_file = {
        "bucket_name": "elasticbeanstalk-fourfront-webdev-wfoutput",
        "workflow_argument_name": "input_pairs",
        "uuid": ["d2c897ec-bdb2-47ce-b1b1-845daccaa571", "d2c897ec-bdb2-47ce-b1b1-845daccaa571"],
        "object_key": ["4DNFI25JXLLI.pairs.gz", "4DNFI25JXLLI.pairs.gz"]
    }
    args = {'input_files': {"some_input": {}, "some_other_input": {}}}
    data = run_awsem_event_data
    tibanna_settings = data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, ff_keys=data.get('ff_keys'),
                      settings=tibanna_settings)
    process_input_file_info(input_file, tibanna.ff_keys, tibanna.env, args)
    assert len(args['input_files']) == 3
    assert 'secondary_files' in args


@valid_env
@pytest.mark.webtest
def test_add_secondary_files_to_args(run_awsem_event_data):
    input_file = {
        "bucket_name": "elasticbeanstalk-fourfront-webdev-wfoutput",
        "workflow_argument_name": "input_pairs",
        "uuid": ["d2c897ec-bdb2-47ce-b1b1-845daccaa571", "d2c897ec-bdb2-47ce-b1b1-845daccaa571"],
        "object_key": ["4DNFI25JXLLI.pairs.gz", "4DNFI25JXLLI.pairs.gz"]
    }
    args = {
        'input_files': {
            'input_pairs': {
                'bucket': 'elasticbeanstalk-fourfront-webdev-wfoutput',
                'object_key': [
                    'd2c897ec-bdb2-47ce-b1b1-845daccaa571/4DNFI25JXLLI.pairs.gz',
                    'd2c897ec-bdb2-47ce-b1b1-845daccaa571/4DNFI25JXLLI.pairs.gz'
                ]
            }
        }
    }
    data = run_awsem_event_data
    tibanna_settings = data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, ff_keys=data.get('ff_keys'),
                      settings=tibanna_settings)
    add_secondary_files_to_args(input_file, tibanna.ff_keys, tibanna.env, args)
