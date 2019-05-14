from core.ec2_utils import update_config


def test_update_config(run_task_awsem_event_data):
    data = run_task_awsem_event_data
    config = data['config']
    update_config(config, data['args']['app_name'], data['args']['input_files'], data['args']['input_parameters'])
    assert config['instance_type'] == 't3.micro'
    assert config['EBS_optimized'] is True
    assert config['ebs_size'] >= 10
    assert config['shutdown_min'] == 30  # check the other fields are preserved in the returned config


def test_update_config2(run_task_awsem_event_data2):
    data = run_task_awsem_event_data2
    config = data['config']
    update_config(config, data['args']['app_name'], data['args']['input_files'], data['args']['input_parameters'])
    assert config['instance_type'] == 't3.xlarge'
    assert config['EBS_optimized'] is True
    assert config['ebs_size'] >= 10
    assert config['shutdown_min'] == 30  # check the other fields are preserved in the returned config


def test_update_config3(run_task_awsem_event_data_chipseq):
    data = run_task_awsem_event_data_chipseq
    config = data['config']
    update_config(config, data['args']['app_name'], data['args']['input_files'], data['args']['input_parameters'])
    assert config['instance_type'] == 'c5.4xlarge'
    assert config['EBS_optimized'] is True
    assert config['ebs_size'] == 87


def test_update_config4(run_task_awsem_event_omit_fields):
    data = run_task_awsem_event_omit_fields
    config = data['config']
    update_config(config, data['args'].get('app_name', ''), data['args']['input_files'], {})
    assert config['instance_type'] == 't3.micro'
    assert config['EBS_optimized'] is True
    assert config['ebs_size'] >= 10
    assert config['shutdown_min'] == "now"


def test_update_config5(run_task_awsem_event_omit_fields2):
    data = run_task_awsem_event_omit_fields2
    config = data['config']
    update_config(config, data['args'].get('app_name', ''), data['args']['input_files'], {})
    assert config['instance_type'] == 't3.micro'
    assert config['EBS_optimized'] is True
    assert config['ebs_size'] >= 10
    assert config['shutdown_min'] == "now"
