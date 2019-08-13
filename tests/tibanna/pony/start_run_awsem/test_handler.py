import pytest
from tibanna_4dn.lambdas.start_run_awsem import (
    handler,
    real_handler
)
from tibanna_4dn.start_run import (
    create_wfr_output_files_and_processed_files,
    user_supplied_proc_file,
    process_input_file_info,
    add_secondary_files_to_args,
    output_target_for_input_extra,
    combine_two,
    run_on_nested_arrays2
)
from ..conftest import valid_env
from tibanna_4dn.pony_utils import TibannaSettings, ProcessedFileMetadata
from dcicutils import ff_utils
import mock
import time


@valid_env
@pytest.mark.webtest
def test_start_awsem_handler(run_awsem_event_data):
    with mock.patch('tibanna_4dn.pony_utils.post_metadata') as mock_request:
        res = handler(run_awsem_event_data, '')
        assert mock_request.call_count == 1  # one for wfr, no pf
    assert(res)
    assert 'ff_meta' in res
    assert 'notes' in res['ff_meta']
    assert 'award' in res['ff_meta']
    assert res['ff_meta']['award'] == '/awards/1U01DA040582-01/'
    assert res['jobid'] == 'somejobid'


@valid_env
@pytest.mark.webtest
def test_start_awsem_handler_processed_files_pf(run_awsem_event_data_processed_files):
    with mock.patch('tibanna_4dn.pony_utils.ProcessedFileMetadata.post') as mock_request:
        res = handler(run_awsem_event_data_processed_files, '')
        assert mock_request.call_count == 1  # one pf (bam).
    assert(res)


@valid_env
@pytest.mark.webtest
def test_start_awsem_handler_processed_files(run_awsem_event_data_processed_files):
    res = real_handler(run_awsem_event_data_processed_files, '')
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
def test_user_supplied_proc_file(run_awsem_event_data_processed_files, proc_file_in_webdev):
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
    tbn = TibannaSettings(env, ff_keys=run_awsem_event_data_processed_files.get('ff_keys'),
                          settings=tibanna_settings)

    file_with_type = proc_file_in_webdev.copy()
    file_with_type['@type'] = ['FileProcessed', 'Item', 'whatever']
    with mock.patch('tibanna_4dn.pony_utils.get_metadata', return_value=file_with_type):
        pf, _ = user_supplied_proc_file(of, 'output_file1', tbn)
        assert type(pf) == ProcessedFileMetadata
        assert pf.as_dict() == proc_file_in_webdev


@pytest.mark.webtest
def test_pseudo_run(run_task_awsem_pseudo_workflow_event_data):
    with mock.patch('tibanna_4dn.pony_utils.post_metadata') as mock_request:
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
    with mock.patch('tibanna_4dn.pony_utils.post_metadata') as mock_request:
        res = handler(run_task_awsem_pseudo_workflow_event_data, '')
        mock_request.assert_called_once()
    assert(res)

    # did we set additional fields correctly
    for k, v in iter(wfr_meta.items()):
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
    res = handler(run_awsem_event_data_processed_files2, '')
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
    tbn = TibannaSettings(env, ff_keys=data.get('ff_keys'),
                          settings=tibanna_settings)
    workflow_uuid = data['workflow_uuid']
    wf_meta = ff_utils.get_metadata(workflow_uuid, key=tbn.ff_keys, ff_env=tbn.env, add_on='frame=object')

    output_files, pf_meta = create_wfr_output_files_and_processed_files(wf_meta, tbn)
    assert(output_files)
    assert len(output_files) == 3
    for of in output_files:
        if of['format'] == 'pairs':
            assert of['secondary_file_formats'] == ['pairs_px2']
            assert of['extra_files']
        else:
            assert 'secondary_files_formats' not in of

    assert(pf_meta)
    assert len(pf_meta) == 3
    for pf in pf_meta:
        pdict = pf.as_dict()
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
    tbn = TibannaSettings(env, ff_keys=data.get('ff_keys'),
                          settings=tibanna_settings)
    workflow_uuid = data['workflow_uuid']
    wf_meta = ff_utils.get_metadata(workflow_uuid, key=tbn.ff_keys, ff_env=tbn.env, add_on='frame=object')

    output_files, pf_meta = create_wfr_output_files_and_processed_files(
        wf_meta, tbn, custom_fields=data.get('custom_pf_fields')
    )
    assert(pf_meta)
    assert(output_files)
    for pf in pf_meta:
        pdict = pf.as_dict()
        assert 'genome_assembly' in pdict
        assert pdict['genome_assembly'] == 'GRCh38'


@valid_env
@pytest.mark.webtest
def test_process_input_file_info(run_awsem_event_data):
    input_file = {
        "bucket_name": "elasticbeanstalk-fourfront-webdev-wfoutput",
        "workflow_argument_name": "input_pairs",
        "uuid": ["d2c897ec-bdb2-47ce-b1b1-845daccaa571", "d2c897ec-bdb2-47ce-b1b1-845daccaa571"],
        "object_key": ["4DNFI25JXLLI.pairs.gz", "4DNFI25JXLLI.pairs.gz"],
        "rename": ["lala.pairs.gz", "haha.pairs.gz"]
    }
    args = {'input_files': {"some_input": {}, "some_other_input": {}}}
    data = run_awsem_event_data
    tibanna_settings = data.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env')
    # tibanna provides access to keys based on env and stuff like that
    tbn = TibannaSettings(env, ff_keys=data.get('ff_keys'),
                          settings=tibanna_settings)
    process_input_file_info(input_file, tbn.ff_keys, tbn.env, args)
    assert len(args['input_files']) == 3
    assert 'secondary_files' in args
    assert 'input_pairs' in args['input_files']
    assert 'rename' in args['input_files']['input_pairs']
    assert args['input_files']['input_pairs']['rename'][1] == 'haha.pairs.gz'


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
    tbn = TibannaSettings(env, ff_keys=data.get('ff_keys'),
                          settings=tibanna_settings)
    add_secondary_files_to_args(input_file, tbn.ff_keys, tbn.env, args)


@valid_env
@pytest.mark.webtest
def test_output_target_for_input_extra():
    tbn = TibannaSettings('fourfront-webdev',
                          settings={"run_type": "bedGraphToBigWig", "env": "fourfront-webdev"})
    target_inf = {'workflow_argument_name': 'bgfile', 'value': '83a80cf8-ca2c-421a-bee9-118bd0572424'}
    of = {'format': 'bw'}

    ff_utils.patch_metadata({'extra_files': []},
                            '83a80cf8-ca2c-421a-bee9-118bd0572424',
                            key=tbn.ff_keys)
    time.sleep(10)
    target_key = output_target_for_input_extra(target_inf, of, tbn)
    assert target_key == '83a80cf8-ca2c-421a-bee9-118bd0572424/4DNFIF14KRAK.bw'

    with pytest.raises(Exception) as expinfo:
        target_key = output_target_for_input_extra(target_inf, of, tbn)
        assert "input already has extra: 'User overwrite_input_extra'" in str(expinfo.value)

    target_key = output_target_for_input_extra(target_inf, of, tbn, True)
    assert target_key == '83a80cf8-ca2c-421a-bee9-118bd0572424/4DNFIF14KRAK.bw'


def test_combine_two():
    x = combine_two('a', 'b')
    assert x == 'a/b'
    x = combine_two(['a1', 'a2'], ['b1', 'b2'])
    assert x == ['a1/b1', 'a2/b2']
    x = combine_two([['a1', 'a2'], ['b1', 'b2']], [['c1', 'c2'], ['d1', 'd2']])
    assert x == [['a1/c1', 'a2/c2'], ['b1/d1', 'b2/d2']]
    x = combine_two([[['a1', 'a2'], ['b1', 'b2']], [['c1', 'c2'], ['d1', 'd2']]],
                    [[['e1', 'e2'], ['f1', 'f2']], [['g1', 'g2'], ['h1', 'h2']]])
    assert x == [[['a1/e1', 'a2/e2'], ['b1/f1', 'b2/f2']],
                 [['c1/g1', 'c2/g2'], ['d1/h1', 'd2/h2']]]


def test_run_on_nested_arrays2():
    def sum0(a, b):
        return(a + b)
    x = run_on_nested_arrays2(1, 2, sum0)
    assert x == 3
    x = run_on_nested_arrays2([1, 2], [3, 4], sum0)
    assert x == [4, 6]
    x = run_on_nested_arrays2([[1, 2], [3, 4]], [[5, 6], [7, 8]], sum0)
    assert x == [[6, 8], [10, 12]]
