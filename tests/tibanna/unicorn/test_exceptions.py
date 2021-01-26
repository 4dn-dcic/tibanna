import pytest
from tibanna.exceptions import (
    AWSEMErrorHandler,
    AWSEMJobErrorException
)


def test_general_awsem_error_msg():
    eh = AWSEMErrorHandler()
    res = eh.general_awsem_error_msg('somejobid')
    assert res == 'Job encountered an error check log using tibanna log --job-id=somejobid [--sfn=stepfunction]'


def test_general_awsem_check_log_msg():
    eh = AWSEMErrorHandler()
    res = eh.general_awsem_check_log_msg('somejobid')
    assert res == 'check log using tibanna log --job-id=somejobid [--sfn=stepfunction]'


def test_awsem_exception_not_enough_space_for_input():
    log = "sometext some text some other text " + \
          "download failed: s3://somebucket/somefile to ../../data1/input/somefile " + \
          "[Errno 28] No space left on device " + \
          "some other text some other text"
    eh = AWSEMErrorHandler()
    res = eh.parse_log(log)
    assert res
    with pytest.raises(AWSEMJobErrorException) as exec_info:
        raise res
    assert 'Not enough space for input files' in str(exec_info.value)


def test_awsem_exception_no_space_for_docker():
    log = "failed to register layer: Error processing tar file(exit status 1): " + \
          "write /miniconda3/pkgs/python-3.7.6-h0371630_2.tar.bz2: no space left on device" + \
          "some text some text"
    eh = AWSEMErrorHandler()
    res = eh.parse_log(log)
    assert res
    with pytest.raises(AWSEMJobErrorException) as exec_info:
        raise res
    assert 'No space for docker' in str(exec_info.value)
    assert 'tar.bz2: no space left' in str(exec_info.value)


def test_awsem_exception_no_space():
    log = '[fputs] No space left on device' + \
          'some text some text'
    eh = AWSEMErrorHandler()
    res = eh.parse_log(log)
    assert res
    with pytest.raises(AWSEMJobErrorException) as exec_info:
        raise res
    assert 'Not enough space' in str(exec_info.value)
    assert '[fputs]' in str(exec_info.value)


def test_awsem_exception_cwl_missing_input():
    log = "Workflow error, try again with --debug for more information:\n" + \
          "Invalid job input record:\n" + \
          "workflow_gatk-GenotypeGVCFs_plus_vcf-integrity-check.cwl:28:5: Missing required input parameter\n" + \
          "                                                     'chromosomes'\n" + \
          "some text some text"
    eh = AWSEMErrorHandler()
    res = eh.parse_log(log)
    assert res
    with pytest.raises(AWSEMJobErrorException) as exec_info:
        raise res
    assert 'CWL missing input' in str(exec_info.value)
    assert 'chromosomes' in str(exec_info.value)


def test_add_custom_errors():
    log = "[M::mem_pestat] low and high boundaries for proper pairs: (1, 22)" + \
          "[mem_sam_pe] paired reads have different names: " + \
          "\"H3MVTCCXX:4:1101:1174861:0\", \"H3MVTCCXX:4:1101:743397:0\""
    eh = AWSEMErrorHandler()
    eh.add_custom_errors([{"error_type": "Unmatching pairs in fastq",
                           "pattern": "paired reads have different names: .+",
                           "multiline": False}])
    assert len(eh.ErrorList) == len(eh._ErrorList) + 1
    res = eh.parse_log(log)
    assert res
    with pytest.raises(AWSEMJobErrorException) as exec_info:
        raise res
    assert 'Unmatching pairs in fastq' in str(exec_info.value)
    assert 'H3MVTCCXX:4:1101:1174861:0' in str(exec_info.value)


def test_add_custom_errors2():
    log = "sometext some text some other text " + \
          "Exception: File is empty (1234567890abcdefg.regionPeak.gz) some other text"
    eh = AWSEMErrorHandler()
    eh.add_custom_errors([{"error_type": "No peak called",
                           "pattern": "Exception: File is empty (.+.regionPeak.gz)"}])
    res = eh.parse_log(log)
    assert res
    with pytest.raises(AWSEMJobErrorException) as exec_info:
        raise res
    assert 'No peak called' in str(exec_info.value)
    assert '1234567890abcdefg.regionPeak.gz' in str(exec_info.value)


def test_no_matching_error():
    log = 'some text some text no error just some text'
    eh = AWSEMErrorHandler()
    res = eh.parse_log(log)
    assert not res
