from core.ec2_utils import update_config, create_json_dict


def test_create_json_dict(run_task_awsem_event_data):
    data = run_task_awsem_event_data
    json = create_json_dict(data)
    assert json
    assert json['Job']['Input']['Env']['TESTENV'] == 1234


def test_update_config(run_task_awsem_event_data):
    data = run_task_awsem_event_data
    config = data['config']
    update_config(config, data['args']['app_name'], data['args']['input_files'], data['args']['input_parameters'])
    assert config['instance_type'] == 't2.micro'
    assert config['EBS_optimized'] is False
    assert config['ebs_size'] >= 10
    assert config['shutdown_min'] == 30  # check the other fields are preserved in the returned config


def test_update_config2(run_task_awsem_event_data2):
    data = run_task_awsem_event_data2
    config = data['config']
    update_config(config, data['args']['app_name'], data['args']['input_files'], data['args']['input_parameters'])
    assert config['instance_type'] == 't2.xlarge'
    assert config['EBS_optimized'] is False
    assert config['ebs_size'] >= 10
    assert config['shutdown_min'] == 30  # check the other fields are preserved in the returned config


def test_update_config3(run_task_awsem_event_data_chipseq):
    data = run_task_awsem_event_data_chipseq
    config = data['config']
    update_config(config, data['args']['app_name'], data['args']['input_files'], data['args']['input_parameters'])
    assert config['instance_type'] == 'c4.4xlarge'
    assert config['EBS_optimized'] is True
    assert config['ebs_size'] == 81
