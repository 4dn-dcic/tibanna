import boto3
import time
import os
import json
from datetime import datetime
from tibanna import create_logger


logger = create_logger('tibanna ' + __name__)


BASE_AMI = 'ami-0885b1f6bd170450c'  # ubuntu 20.04 for us-east-1
USERDATA_DIR = os.path.dirname(os.path.abspath(__file__))
USERDATA_FILE = os.path.join(USERDATA_DIR, 'create_ami_userdata')
AMI_NAME = 'tibanna-ami-' + datetime.strftime(datetime.today(), '%Y%m%d')  # e.g tibanna-ami-20201113


def launch_instance_for_tibanna_ami(keyname, userdata_file=USERDATA_FILE, base_ami=BASE_AMI):

    launch_args = {'ImageId': base_ami,
                   'InstanceType': 't3.micro',
                   'MaxCount': 1,
                   'MinCount': 1,
                   'TagSpecifications': [{'ResourceType': 'instance',
                                          'Tags': [{"Key": "Name", "Value": "tibanna_ami"}]}]}
    if userdata_file:
        with open(userdata_file, 'r') as f:
            userdata_str = f.read()
        launch_args.update({'UserData': userdata_str})

    if keyname:
        launch_args.update({'KeyName': keyname})

    logger.debug("launch_args=" + str(launch_args))
    ec2 = boto3.client('ec2')
    res = ec2.run_instances(**launch_args)
    logger.debug("response from EC2 run_instances :" + str(res) + '\n\n')
    instance_id = res['Instances'][0]['InstanceId']

    return instance_id


def create_ami_from_tibanna(keyname,
                            userdata_file=USERDATA_FILE,
                            base_ami=BASE_AMI,
                            ami_name=AMI_NAME,
                            make_public=False,
                            base_region='us-east-1'):

    if not userdata_file:
        logger.info("no userdata.. no need to launch an instance.. just copying image")
        ec2 = boto3.client('ec2')
        try:
            res_copy = ec2.copy_image(Name=ami_name, SourceImageId=base_ami, SourceRegion=base_region)
        except:
            raise Exception("Failed to copy image")

        logger.info("waiting for 10min for the image to be created..")
        time.sleep(10 * 60)

        new_image_id = res_copy['ImageId']

        if make_public:
            ec2.modify_image_attribute(ImageId=new_image_id,
                                       LaunchPermission={'Add': [{'Group': 'all'}]})
        return new_image_id

    # launch an instance
    try:
        instance_id = launch_instance_for_tibanna_ami(keyname, userdata_file, base_ami)
        logger.debug("instance_id=" + instance_id)
    except:
        raise Exception("Failed to launch an instance")

    logger.info("waiting for 10min for the instance to install everything and reboot..")
    time.sleep(10 * 60)

    # create an image from the instance
    try:
        create_image_args = {'InstanceId': instance_id, 'Name':  ami_name}
        ec2 = boto3.client('ec2')
        logger.info("creating an image...")
        res_create = ec2.create_image(**create_image_args)
    except:
        raise Exception("Failed to create an image")

    logger.info("waiting for 10min for the image to be created..")
    time.sleep(10 * 60)

    try:
        ec2.terminate_instances(InstanceIds=[instance_id])
    except:
        raise Exception("Failed to terminate the instance")

    new_image_id = res_create['ImageId']

    if make_public:
        ec2.modify_image_attribute(ImageId=new_image_id,
                                   LaunchPermission={'Add': [{'Group': 'all'}]})
    return new_image_id


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Arguments")
    parser.add_argument("-k", "--key_name", help="key_name (default: no key)", default="")
    parser.add_argument("-a", "--ami_name", help="ami_name (default: 'tibanna-ami-<date>'", default="")
    parser.add_argument("-b", "--base-ami",
                        help="base ami (default: ubuntu 20.04 for us-east-1 ('ami-0885b1f6bd170450c')",
                        default=BASE_AMI)
    parser.add_argument("-e", "--no-user-data", help="do not use userdata", action="store_true")
    parser.add_argument("-p", "--make-public", help="make the new AMI public", action="store_true")
    args = parser.parse_args()

    if args.no_user_data:
        new_image_id = create_ami_from_tibanna(args.key_name, ami_name=args.ami_name, userdata_file='',
                                               base_ami=args.base_ami, make_public=args.make_public)
    else:
        new_image_id = create_ami_from_tibanna(args.key_name, ami_name=args.ami_name, base_ami=args.base_ami,
                                               make_public=args.make_public)
    logger.info("new_image_id=" + new_image_id)

