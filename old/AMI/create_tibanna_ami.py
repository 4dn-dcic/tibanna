import boto3
import time


def launch_instance_for_tibanna_ami(keyname, userdata_file='AMI/tibanna_ami.sh'):

    amazon_linux_ami_id = 'ami-4fffc834'

    with open(userdata_file, 'r') as f:
        userdata_str = f.read()
    # print(userdata_str)

    launch_args = {'ImageId': amazon_linux_ami_id,
                   'InstanceType': 't2.micro',
                   'UserData': userdata_str,
                   'MaxCount': 1,
                   'MinCount': 1,
                   'MetadataOptions': {
                       'HttpTokens': 'required',
                       'HttpEndpoint': 'enabled',
                       'HttpPutResponseHopLimit': 2
                    },
                   'TagSpecifications': [{'ResourceType': 'instance',
                                          'Tags': [{"Key": "Name", "Value": "tibanna_ami"}]}]}
    if keyname:
        launch_args.update({'KeyName': keyname})

    ec2 = boto3.client('ec2')
    res = ec2.run_instances(**launch_args)
    instance_id = res['Instances'][0]['InstanceId']

    return instance_id


def create_ami_from_tibanna(keyname,
                            userdata_file='AMI/tibanna_ami.sh',
                            ami_name='docker_cwlrunner2'):

    # launch an instance
    try:
        instance_id = launch_instance_for_tibanna_ami(keyname, userdata_file)
    except:
        Exception("Failed to launch an instance")

    print("waiting for 10min for the instance to install everything and reboot..")
    time.sleep(10 * 60)

    # create an image from the instance
    try:
        create_image_args = {'InstanceId': instance_id, 'Name':  ami_name}
        ec2 = boto3.client('ec2')
        print("creating an image...")
        res = ec2.create_image(**create_image_args)
    except:
        Exception("Failed to create an image")
    print(res)

    print("waiting for 10min for the image to be created..")
    time.sleep(10 * 60)

    try:
        res_term = ec2.terminate_instances(InstanceIds=[instance_id])
    except:
        Exception("Failed to terminate the instance")
    print(res_term)

    return({"create_image": res, "terminate_instance": res_term})


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Arguments")
    parser.add_argument("-k", "--key_name", help="key_name")
    parser.add_argument("-a", "--ami_name", help="ami_name")
    args = parser.parse_args()

    res = create_ami_from_tibanna(args.key_name, ami_name=args.ami_name)
