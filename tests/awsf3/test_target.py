import pytest
from awsf3.target import (
    Target,
    SecondaryTarget,
    SecondaryTargetList,
    create_out_meta
)
from tests.awsf3.conftest import upload_test_bucket
import boto3


def test_target_init():
    target = Target('some_bucket')
    assert target.bucket == 'some_bucket'
    assert target.unzip is False
    assert not target.is_valid()  # source/dest not set yet

def test_target_parse_target_value_str_object_key():
    target = Target('some_bucket')
    target.parse_target_value('some_object_key')
    assert target.dest == 'some_object_key'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False

def test_target_parse_target_value_str_url():
    target = Target('some_bucket')
    target.parse_target_value('s3://another_bucket/some_object_key')
    assert target.dest == 'some_object_key'
    assert target.bucket == 'another_bucket'
    assert target.unzip is False

def test_target_parse_target_value_dict_object_key():
    target = Target('some_bucket')
    target.parse_target_value({'object_key': 'some_object_key'})
    assert target.dest == 'some_object_key'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False

def test_target_parse_target_value_dict_object_key_bucket():
    target = Target('some_bucket')
    target.parse_target_value({'object_key': 'some_object_key', 'bucket_name': 'another_bucket'})
    assert target.dest == 'some_object_key'
    assert target.bucket == 'another_bucket'
    assert target.unzip is False

def test_target_parse_target_value_dict_object_prefix():
    target = Target('some_bucket')
    target.parse_target_value({'object_prefix': 'some_dir/'})
    assert target.dest == 'some_dir/'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False

def test_target_parse_target_value_dict_object_prefix_wo_slash():
    target = Target('some_bucket')
    target.parse_target_value({'object_prefix': 'some_dir'})
    assert target.dest == 'some_dir/'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False

def test_target_parse_target_value_unzip():
    target = Target('some_bucket')
    target.parse_target_value({'unzip': True, 'object_prefix': 'some_dir/'})
    assert target.dest == 'some_dir/'
    assert target.bucket == 'some_bucket'
    assert target.unzip is True

def test_target_parse_target_value_unzip_wo_prefix():
    target = Target('some_bucket')
    with pytest.raises(Exception) as ex:
        target.parse_target_value({'unzip': True, 'object_key': 'some_object_key'})
    assert 'prefix' in str(ex)

def test_target_parse_target_value_object_key_prefix_conflict():
    target = Target('some_bucket')
    with pytest.raises(Exception) as ex:
        target.parse_target_value({'object_prefix': 'some_dir/', 'object_key': 'some_object_key'})
    assert 'not both' in str(ex)

def test_target_parse_custom_target_str_object_key():
    target = Target('some_bucket')
    target.parse_custom_target(target_key='file:///data1/out/somefile',
                               target_value='some_object_key')
    assert target.dest == 'some_object_key'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False
    assert target.source == '/data1/out/somefile'
    assert target.source_name == 'somefile'

def test_target_parse_custom_target_str_url():
    target = Target('some_bucket')
    target.parse_custom_target(target_key='file:///data1/out/somefile',
                               target_value='s3://another_bucket/some_object_key')
    assert target.dest == 'some_object_key'
    assert target.bucket == 'another_bucket'
    assert target.unzip is False
    assert target.source == '/data1/out/somefile'

def test_target_parse_custom_target_dict_object_key():
    target = Target('some_bucket')
    target.parse_custom_target(target_key='file:///data1/out/somefile',
                               target_value={'object_key': 'some_object_key'})
    assert target.dest == 'some_object_key'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False
    assert target.source == '/data1/out/somefile'

def test_target_parse_custom_target_null_target_value():
    # target value must be given
    target = Target('some_bucket')
    with pytest.raises(Exception) as ex:
        target.parse_custom_target(target_key='file:///data1/out/somefile',
                                   target_value=None)
    assert 'target' in str(ex)

def test_target_parse_cwl_target_str_object_key():
    target = Target('some_bucket')
    target.parse_cwl_target(target_key='some_argname',
                            target_value='some_object_key',
                            output_meta={'some_argname': {'path': '/data1/out/1/somefile'}})
    assert target.dest == 'some_object_key'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False
    assert target.source == '/data1/out/1/somefile'

def test_target_parse_cwl_target_dict_object_key():
    target = Target('some_bucket')
    target.parse_cwl_target(target_key='some_argname',
                            target_value={'object_key': 'some_object_key'},
                            output_meta={'some_argname': {'path': '/data1/out/1/somefile'}})
    assert target.dest == 'some_object_key'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False
    assert target.source == '/data1/out/1/somefile'

def test_target_parse_cwl_target_null_target_value():
    target = Target('some_bucket')
    target.parse_cwl_target(target_key='some_argname',
                            target_value=None,
                            output_meta={'some_argname': {'path': '/data1/out/1/somefile'}})
    # use sourcename as dest if target_value is not given
    assert target.dest == '1/somefile'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False
    assert target.source == '/data1/out/1/somefile'

def test_target_sourcename():
    target = Target('some_bucket')
    target.source = '/data1/out/somefile'
    assert target.source_name == 'somefile'

def test_target_sourcename2():
    target = Target('some_bucket')
    target.source = '/data1/out/1/somefile'
    assert target.source_name == '1/somefile'

def test_target_sourcename3():
    target = Target('some_bucket')
    target.source = '/data1/shell/1/somefile'
    assert target.source_name == '1/somefile'

def test_target_sourcename4():
    target = Target('some_bucket')
    target.source = '/data1/whatever/1/somefile'
    assert target.source_name == 'whatever/1/somefile'

def test_target_is_valid():
    target = Target('some_bucket')
    target.source = '/data1/whatever/1/somefile'
    target.dest = 'some_dest'
    assert target.is_valid()

def test_target_is_valid():
    target = Target('some_bucket')
    target.source = '/data1/whatever/1/somefile'
    assert not target.is_valid()  # no destination set

def test_target_is_valid():
    target = Target('some_bucket')
    target.dest = 'some_dest'
    assert not target.is_valid()  # no source set

def test_target_as_dict():
    target = Target('some_bucket')
    target.dest = 'some_dest'
    target.source = 'some_source'
    assert target.as_dict() == {'source': 'some_source',
                                'dest': 'some_dest',
                                'bucket': 'some_bucket',
                                'unzip': False}

def test_secondary_target_is_matched():
    st = SecondaryTarget('some_bucket')
    st.dest = 'some_dest.abc'
    assert st.is_matched('some_source.abc')

def test_secondary_target_is_not_matched():
    st = SecondaryTarget('some_bucket')
    st.dest = 'some_dest.abc'
    assert not st.is_matched('some_source.def')

def test_secondary_target_list_init():
    stlist = SecondaryTargetList('some_bucket')
    assert stlist.n == 0
    assert stlist.secondary_targets == []
    assert stlist.bucket == 'some_bucket'

def test_secondary_target_list_parse_target_values_1_str_object_key():
    # an output target with one secondary target
    stlist = SecondaryTargetList('some_bucket')
    stlist.parse_target_values(['some_secondary_object_key'])
    assert len(stlist.secondary_targets) == 1
    assert stlist.n == 1
    assert stlist.secondary_targets[0].dest == 'some_secondary_object_key'
    assert stlist.secondary_targets[0].bucket == 'some_bucket'

def test_secondary_target_list_parse_target_values_2_str_object_key():
    # an output target with two secondary targets
    stlist = SecondaryTargetList('some_bucket')
    stlist.parse_target_values(['some_secondary_object_key', 'another_secondary_object_key'])
    assert len(stlist.secondary_targets) == 2
    assert stlist.n == 2
    assert stlist.secondary_targets[0].dest == 'some_secondary_object_key'
    assert stlist.secondary_targets[1].dest == 'another_secondary_object_key'
    assert stlist.secondary_targets[0].bucket == 'some_bucket'
    assert stlist.secondary_targets[1].bucket == 'some_bucket'

def test_secondary_target_list_parse_target_values_2_str_url():
    # an output target with two secondary targets 
    stlist = SecondaryTargetList('some_bucket')
    stlist.parse_target_values(['some_secondary_object_key', 's3://another_bucket/another_secondary_object_key'])
    assert len(stlist.secondary_targets) == 2
    assert stlist.n == 2
    assert stlist.secondary_targets[0].dest == 'some_secondary_object_key'
    assert stlist.secondary_targets[1].dest == 'another_secondary_object_key'
    assert stlist.secondary_targets[0].bucket == 'some_bucket'
    assert stlist.secondary_targets[1].bucket == 'another_bucket'

def test_secondary_target_list_reorder_by_source_same_number():
    stlist = SecondaryTargetList('some_bucket')
    stlist.parse_target_values(['somefile.abc', 's3://another_bucket/somefile.def', {'object_key': 'somefile.ghi'}])
    stlist.reorder_by_source(['somesource.def', 'somesource.abc', 'somesource.jkl', 'somesource.ghi'])
    assert stlist.n == 4
    assert len(stlist.secondary_targets) == 4
    assert stlist.secondary_targets[0].dest == 'somefile.def'
    assert stlist.secondary_targets[1].dest == 'somefile.abc'
    assert stlist.secondary_targets[2].dest == 'somesource.jkl'  # inserted
    assert stlist.secondary_targets[3].dest == 'somefile.ghi'
    assert stlist.secondary_targets[0].bucket == 'another_bucket'  # bucket should be reordered, too.
    assert stlist.secondary_targets[1].bucket == 'some_bucket'
    assert stlist.secondary_targets[2].bucket == 'some_bucket'
    assert stlist.secondary_targets[3].bucket == 'some_bucket'
    assert stlist.secondary_targets[0].source == 'somesource.def'
    assert stlist.secondary_targets[1].source == 'somesource.abc'
    assert stlist.secondary_targets[2].source == 'somesource.jkl'
    assert stlist.secondary_targets[3].source == 'somesource.ghi'

def test_secondary_target_list_as_dict():
    stlist = SecondaryTargetList('some_bucket')
    stlist.parse_target_values(['somefile.abc', 'somefile.def'])
    stlist.reorder_by_source(['somesource.def', 'somesource.abc'])
    assert stlist.n == 2
    assert stlist.as_dict() == [stlist.secondary_targets[0].as_dict(),
                                stlist.secondary_targets[1].as_dict()]

def test_create_out_meta_cwl():
    md5dict = {'path1': '683153f0051fef9e778ce0866cfd97e9', 'path2': 'c14105f8209836cd3b1cc1b63b906fed'}
    outmeta = create_out_meta('cwl', {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}}, md5dict=md5dict)
    assert outmeta == {'arg1': {'path': 'path1', 'md5sum': md5dict['path1']},
                       'arg2': {'path': 'path2', 'md5sum': md5dict['path2']}}

def test_create_out_meta_cwl_secondary_files():
    md5dict = {'path1': '683153f0051fef9e778ce0866cfd97e9', 'path2': 'c14105f8209836cd3b1cc1b63b906fed'}
    outmeta = create_out_meta('cwl', {'arg1': {'path': 'path1', 'secondaryFiles': [{'path': 'path2'}]}}, md5dict=md5dict)
    assert outmeta == {'arg1': {'path': 'path1', 'md5sum': md5dict['path1'],
                                'secondaryFiles': [{'path': 'path2', 'md5sum': md5dict['path2']}]}}

def test_create_out_meta_cwl_no_md5():
    outmeta = create_out_meta('cwl', {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}})
    assert outmeta == {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}}

def test_create_out_meta_cwl_no_execution_metadata():
    with pytest.raises(Exception) as ex:
        outmeta = create_out_meta('cwl')
    assert 'execution_metadata' in str(ex)

def test_create_out_meta_wdl():
    md5dict = {'path1': '683153f0051fef9e778ce0866cfd97e9', 'path2': 'c14105f8209836cd3b1cc1b63b906fed'}
    outmeta = create_out_meta('wdl', {'outputs': {'arg1': 'path1', 'arg2': 'path2'}}, md5dict=md5dict)
    assert outmeta == {'arg1': {'path': 'path1', 'md5sum': md5dict['path1']},
                       'arg2': {'path': 'path2', 'md5sum': md5dict['path2']}}

def test_create_out_meta_wdl_no_md5():
    outmeta = create_out_meta('wdl', {'outputs': {'arg1': 'path1', 'arg2': 'path2'}})
    assert outmeta == {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}}

def test_create_out_meta_wdl_no_execution_metadata():
    with pytest.raises(Exception) as ex:
        outmeta = create_out_meta('wdl')
    assert 'execution_metadata' in str(ex)

def test_create_out_meta_snakemake():
    outmeta = create_out_meta('snakemake')
    assert outmeta == {}

def test_create_out_meta_shell():
    outmeta = create_out_meta('shell')
    assert outmeta == {}

def test_upload_file():
    target = Target(upload_test_bucket)
    target.source = 'tests/awsf3/test_files/some_test_file_to_upload'
    target.dest = 'some_test_object_key'
    target.upload_to_s3()
    s3 = boto3.client('s3')
    res = s3.get_object(Bucket=upload_test_bucket, Key='some_test_object_key')
    assert res['Body'].read().decode('utf-8') == 'abcd\n'
    s3.delete_object(Bucket=upload_test_bucket, Key='some_test_object_key')
    with pytest.raises(Exception) as ex:
        res = s3.get_object(Bucket=upload_test_bucket, Key='some_test_object_key')
    assert 'NoSuchKey' in str(ex)

def test_upload_dir():
    target = Target(upload_test_bucket)
    target.source = 'tests/awsf3/test_files/some_test_dir_to_upload'  # has two files and one subdir
    target.dest = 'some_test_object_prefix'
    target.upload_to_s3()
    s3 = boto3.client('s3')

    def test_and_delete_key(key):
        res = s3.get_object(Bucket=upload_test_bucket, Key=key)
        assert res['Body'].read()
        s3.delete_object(Bucket=upload_test_bucket, Key=key)
        with pytest.raises(Exception) as ex:
            res = s3.get_object(Bucket=upload_test_bucket, Key=key)
        assert 'NoSuchKey' in str(ex)

    test_and_delete_key('some_test_object_prefix/file1')
    test_and_delete_key('some_test_object_prefix/file2')
    test_and_delete_key('some_test_object_prefix/dir1/file1')


def test_upload_file_err():
    target = Target(upload_test_bucket)
    target.source = 'some_test_file_that_does_not_exist'
    target.dest = 'whatever'
    with pytest.raises(Exception) as ex:
        target.upload_to_s3()
    assert 'failed to upload output file some_test_file_that_does_not_exist' + \
           ' to %s/whatever' % upload_test_bucket in str(ex)
