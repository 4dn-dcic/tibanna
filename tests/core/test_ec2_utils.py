from core.ec2_utils import Awsem, update_config


def test_create_awsem(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    assert awsem.args
    assert awsem.config
    assert awsem.app_name
    assert awsem.output_s3
    assert awsem.output_files_meta


def test_get_output_files(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    of = awsem.output_files()
    first_key = of.keys()[0]
    assert 1 == len(of)
    assert of[first_key].runner == awsem
    assert of[first_key].bucket == awsem.output_s3
    assert of[first_key].key == 'lalala/md5_report'
    assert of[first_key].output_type == 'Output report file'


def test_get_input_files(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    infiles = awsem.input_files()
    first_key = infiles.keys()[0]
    assert 1 == len(infiles)
    assert infiles[first_key].runner == awsem
    assert infiles[first_key].bucket == 'elasticbeanstalk-fourfront-webdev-files'
    assert infiles[first_key].key == 'f4864029-a8ad-4bb8-93e7-5108f462ccaa/4DNFIRSRJH45.fastq.gz'
    assert infiles[first_key].accession == '4DNFIRSRJH45'


def test_get_inputfile_accession(update_ffmeta_event_data, tibanna_env):
    update_ffmeta_event_data.update(tibanna_env)
    awsem = Awsem(update_ffmeta_event_data)
    assert awsem.inputfile_accessions['input_file'] == '4DNFIRSRJH45'


def test_update_config(run_task_awsf_event_data):
    data = run_task_awsf_event_data
    config = data['config']
    update_config(config, data['args']['app_name'], data['args']['input_files'], data['args']['input_parameters'])
    assert config['instance_type'] == 't2.micro'
    assert config['EBS_optimized'] is False
    assert config['ebs_size'] >= 10
    assert config['copy_to_s3'] is True  # check the other fields are preserved in the returned config
