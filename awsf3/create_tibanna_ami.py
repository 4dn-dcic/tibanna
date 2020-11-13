import boto3
import time
import os
from datetime import datetime


BASE_AMI = 'ami-0885b1f6bd170450c'  # ubuntu 20.04
USERDATA_DIR = os.path.dirname(os.path.abspath(__file__))
USERDATA_FILE = os.path.join(USERDATA_DIR, 'create_ami_userdata')
AMI_NAME = 'tibanna-ami-' + datetime.strftime(datetime.today(), '%Y%m%d')  # e.g tibanna-ami-20201113


def launch_instance_for_tibanna_ami(keyname, userdata_file=USERDATA_FILE):

    with open(userdata_file, 'r') as f:
        userdata_str = f.read()

    launch_args = {'ImageId': BASE_AMI,
                   'InstanceType': 't3.micro',
                   'UserData': userdata_str,
                   'MaxCount': 1,
                   'MinCount': 1,
                   'TagSpecifications': [{'ResourceType': 'instance',
                                          'Tags': [{"Key": "Name", "Value": "tibanna_ami"}]}]}
    if keyname:
        launch_args.update({'KeyName': keyname})

    ec2 = boto3.client('ec2')
    res = ec2.run_instances(**launch_args)
    instance_id = res['Instances'][0]['InstanceId']

    return instance_id


def create_ami_from_tibanna(keyname,
                            userdata_file=USERDATA_FILE,
                            ami_name=AMI_NAME):

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
