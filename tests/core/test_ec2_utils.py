from core.ec2_utils import Awsem


def test_create_awsem(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    assert awsem.args
    assert awsem.config
    assert awsem.app_name
    assert awsem.output_s3


def test_get_output_files(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    of = awsem.output_files()
    first_key = of.keys()[0]
    assert 1 == len(of)
    assert of[first_key].runner == awsem
    assert of[first_key].bucket == awsem.output_s3
    assert of[first_key].key == 'lalala/md5_report'


def test_get_input_files(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    infiles = awsem.input_files()
    assert 1 == len(infiles)
    assert infiles[0].runner == awsem
    assert infiles[0].bucket == 'elasticbeanstalk-fourfront-webdev-files'
    assert infiles[0].key == 'f4864029-a8ad-4bb8-93e7-5108f462ccaa/4DNFIRSRJH45.fastq.gz'
    assert infiles[0].accession == '4DNFIRSRJH45'


def test_get_inputfile_accession(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    assert awsem.inputfile_accession == '4DNFIRSRJH45'
