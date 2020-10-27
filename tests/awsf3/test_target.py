import io
import boto3
import pytest
from awsf3.target import (
    Target,
    SecondaryTarget,
    SecondaryTargetList
)
from tibanna.awsem import (
    AwsemPostRunJsonOutputFile
)
from tests.awsf3.conftest import upload_test_bucket, CaptureOut


def test_target_init():
    target = Target('some_bucket')
    assert target.bucket == 'some_bucket'
    assert target.unzip is False
    assert target.is_valid is False  # source/dest not set yet


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


def test_target_parse_target_value_dict_object_key_err():
    target = Target('some_bucket')
    with pytest.raises(Exception) as ex:
        target.parse_target_value({'object_key': 'some_object_key/'})
    assert 'object_prefix' in str(ex)


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
    outfile = AwsemPostRunJsonOutputFile(**{'path': '/data1/out/1/somefile'})
    target.parse_cwl_target(target_key='some_argname',
                            target_value='some_object_key',
                            prj_output_files={'some_argname': outfile})
    assert target.dest == 'some_object_key'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False
    assert target.source == '/data1/out/1/somefile'


def test_target_parse_cwl_target_dict_object_key():
    target = Target('some_bucket')
    outfile = AwsemPostRunJsonOutputFile(**{'path': '/data1/out/1/somefile'})
    target.parse_cwl_target(target_key='some_argname',
                            target_value={'object_key': 'some_object_key'},
                            prj_output_files={'some_argname': outfile})
    assert target.dest == 'some_object_key'
    assert target.bucket == 'some_bucket'
    assert target.unzip is False
    assert target.source == '/data1/out/1/somefile'


def test_target_parse_cwl_target_null_target_value():
    target = Target('some_bucket')
    outfile = AwsemPostRunJsonOutputFile(**{'path': '/data1/out/1/somefile'})
    target.parse_cwl_target(target_key='some_argname',
                            target_value=None,
                            prj_output_files={'some_argname': outfile})
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
    assert target.is_valid is True


def test_target_is_valid():
    target = Target('some_bucket')
    target.source = '/data1/whatever/1/somefile'
    assert target.is_valid is False  # no destination set


def test_target_is_valid():
    target = Target('some_bucket')
    target.dest = 'some_dest'
    assert target.is_valid is False  # no source set


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


def test_upload_file_prefix():
    target = Target(upload_test_bucket)
    target.source = 'tests/awsf3/test_files/some_test_file_to_upload'
    target.dest = 'some_test_object_prefix/'
    target.upload_to_s3()
    s3 = boto3.client('s3')
    res = s3.get_object(Bucket=upload_test_bucket, Key='some_test_object_prefix/tests/awsf3/test_files/some_test_file_to_upload')
    assert res['Body'].read().decode('utf-8') == 'abcd\n'
    s3.delete_object(Bucket=upload_test_bucket, Key='some_test_object_prefix/tests/awsf3/test_files/some_test_file_to_upload')
    with pytest.raises(Exception) as ex:
        res = s3.get_object(Bucket=upload_test_bucket, Key='some_test_object_prefix/tests/awsf3/test_files/some_test_file_to_upload')
    assert 'NoSuchKey' in str(ex)


def test_upload_dir():
    target = Target(upload_test_bucket)
    target.source = 'tests/awsf3/test_files/some_test_dir_to_upload'  # has two files and one subdir
    target.dest = 'some_test_object_prefix/'
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


def test_upload_zip():
    target = Target(upload_test_bucket)
    target.source = 'tests/awsf3/test_files/some_zip_file_to_upload.zip'  # has two files and one subdir
    target.dest = 'some_test_object_prefix/'
    target.unzip = True
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


def test_upload_zip_not_a_zip_file_err():
    target = Target(upload_test_bucket)
    target.source = 'tests/awsf3/test_files/some_test_file_to_upload'  # not a zip file
    target.dest = 'some_test_object_prefix/'
    target.unzip = True
    with pytest.raises(Exception) as ex:
        target.upload_to_s3()
    assert 'not a zip file' in str(ex)


def test_upload_zip_not_a_zip_file_err2():
    target = Target(upload_test_bucket)
    target.source = 'some_test_file_that_does_not_exist'
    target.dest = 'some_test_object_prefix/'
    target.unzip = True
    with pytest.raises(Exception) as ex:
        target.upload_to_s3()
    assert 'FileNotFound' in str(ex)


def test_upload_zip_directory_conflict(capsys):
    target = Target(upload_test_bucket)
    target.source = 'tests/awsf3/test_files/some_test_dir_to_upload'  # has two files and one subdir
    target.dest = 'some_test_object_prefix/'
    target.unzip = True  # conflict, since the source is a directory

    # test stdout
    cap = CaptureOut()
    with cap:
        target.upload_to_s3()
    assert 'Warning' in cap.get_captured_out()
    
    # still the directory should be uploaded despite the unzip conflict
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
