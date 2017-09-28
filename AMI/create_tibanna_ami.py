def launch_instance_for_tibanna_ami(keyname, userdata_file='AMI/tibanna_ami.sh'):

    amazon_linux_ami_id='ami-4fffc834'
    
    with open(userdata_file, 'r') as f:
        userdata_str=f.read().replace('\n', '')
    
    launch_args = {'ImageId': amazon_linux_ami_id,
                                   'InstanceType': 't2.micro',
                                   'UserData': userdata_str,
                                   'MaxCount': 1,
                                   'MinCount': 1,
                                   'TagSpecifications': [{'ResourceType': 'instance',
                                              "Tags": [{"Key": "Name", "Value": "tibanna_ami"}]}]
                                   }
    if key_name:
        launch_args.update({'KeyName': key_name})
    
    ec2 = boto3.client('ec2')
    res = ec2.run_instances(**launch_args)
    instance_id = res['Instances'][0]['InstanceId']
    
    return instance_id


def create_ami_from_tibanna(keyname, 
                            userdata_file='AMI/tibanna_ami.sh',
                            ami_name='docker_cwlrunner2'):

    # launch an instance
    instance_id = launch_instance_for_tibanna_ami(keyname, userdata_file)

    sleep(20)
    
    # create an image from the instance
    create_image_args = {'InstanceId': instance_id, 'Name':  ami_name}
    res = ec2.create_image(**create_image_args)
    
    return(res)


