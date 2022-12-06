import boto3
import time
import os
from datetime import datetime
from tibanna import create_logger
from tibanna.vars import AMI_PER_REGION


logger = create_logger(__name__)


class AMI(object):

    BASE_AMI = None
    BASE_AMI_X86 = 'ami-0885b1f6bd170450c'  # ubuntu 20.04 for us-east-1 (x86)
    BASE_AMI_ARM = 'ami-00266f51b6b22db58'  # ubuntu 20.04 for us-east-1 (Arm)
    BASE_REGION = 'us-east-1'
    USERDATA_DIR = os.path.dirname(os.path.abspath(__file__))
    USERDATA_FILE = os.path.join(USERDATA_DIR, 'create_ami_userdata')
    AMI_NAME = 'tibanna-ami-' + datetime.strftime(datetime.today(), '%Y%m%d')  # e.g tibanna-ami-20201113
    ARCHITECTURE = 'x86'

    def __init__(self, base_ami=None, base_region=None, userdata_file=None, ami_name=None, architecture=None):
        if base_ami:
            self.BASE_AMI = base_ami
        elif architecture == 'x86':
            self.BASE_AMI = self.BASE_AMI_X86
            self.AMI_NAME = 'tibanna-ami-x86-' + datetime.strftime(datetime.today(), '%Y%m%d')
        elif architecture == 'Arm':
            self.BASE_AMI = self.BASE_AMI_ARM
            self.AMI_NAME = 'tibanna-ami-arm-' + datetime.strftime(datetime.today(), '%Y%m%d')
            self.ARCHITECTURE = 'Arm'


        if base_region:
            self.BASE_REGION = base_region
        if userdata_file is not None:
            self.USERDATA_FILE = userdata_file
        if ami_name:
            self.AMI_NAME = ami_name

    @staticmethod
    def launch_instance_for_tibanna_ami(keyname, userdata_file, base_ami, architecture):

        instanceType = 't3.micro'
        if architecture == 'Arm':
            instanceType = 'a1.medium'

        launch_args = {'ImageId': base_ami,
                       'InstanceType': instanceType,
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

    def create_ami_for_tibanna(self, keyname=None, make_public=False, replicate=False):
        return self.create_ami(keyname=keyname, userdata_file=self.USERDATA_FILE,
                               base_ami=self.BASE_AMI, ami_name=self.AMI_NAME,
                               make_public=make_public, base_region=self.BASE_REGION, 
                               replicate=replicate, architecture=self.ARCHITECTURE)

    @staticmethod
    def replicate_ami(*, ami_name, ami_id, source_region='us-east-1',
                      target_regions=None,
                      make_public=True):
        """ Replicates the given ami_id from the source region into the target region(s).

            Params:
                ami_name (str): Name to use with AMI, typically something like tibanna-ami-20211025
                ami_id (str): The AMI ID from AWS for the source image
                source_region (str): The region the source AMI was created in
                target_regions (str[]): List of regions to replicate the source AMI into
                                        Leave as None to use all regions in AMI_PER_REGION
                make_public (bool, default True): whether or not this AMI should be public

            Raises ClientError if a boto3 call fails.
            Returns an AMI_PER_REGION mapping
        """
        if not target_regions:
            target_regions = [r for r in AMI_PER_REGION['x86'].keys() if r != source_region]

        # Create sessions in each target region and copy the AMI into it
        # If this AMI is to be publicly available, sleep for 5 mins to allow
        # the AMI to be registered, then modify attribution to public.
        ami_per_region = {}
        for region in target_regions:
            region_session = boto3.client('ec2', region_name=region)
            response = region_session.copy_image(
                Name=ami_name,
                Description=f'{ami_name} replicated from {source_region}',
                SourceImageId=ami_id,
                SourceRegion=source_region
            )
            new_image_id = response['ImageId']
            logger.info(f'Copied {ami_name} from {source_region} to {region}'
                        f' under new AMI ID {new_image_id}')
            ami_per_region[region] = new_image_id

        if make_public:
            logger.info('Provisioning PUBLIC AMIs - sleeping 5 mins, ctrl-c now if unintended')
            time.sleep(5 * 60)
            for region, image_id in ami_per_region.items():
                region_session = boto3.client('ec2', region_name=region)  # re-create since its been some time
                region_session.modify_image_attribute(ImageId=image_id,
                                                      LaunchPermission={'Add': [{'Group': 'all'}]})
        else:
            logger.info(f'Provisioning private AMIs')

        logger.info(f'Provisioned {ami_per_region}')
        return ami_per_region

    @classmethod
    def create_ami(cls, keyname=None, userdata_file=USERDATA_FILE,
                   base_ami=BASE_AMI,
                   ami_name=AMI_NAME,
                   make_public=False,
                   replicate=False,
                   architecture='x86',
                   base_region='us-east-1'):
        """ Helper function that creates the Tibanna AMI from a base image. """
        if not userdata_file:
            logger.info("no userdata.. no need to launch an instance.. just copying image")
            ec2 = boto3.client('ec2')
            try:
                res_copy = ec2.copy_image(Name=ami_name, SourceImageId=base_ami, SourceRegion=base_region)
            except:
                raise Exception("Failed to copy image")

            # I tried 5 min - it's not enough and it fails at the next step.
            logger.info("waiting for 10min for the image to be created..")
            time.sleep(10 * 60)

            new_image_id = res_copy['ImageId']

            if make_public:
                ec2.modify_image_attribute(ImageId=new_image_id,
                                           LaunchPermission={'Add': [{'Group': 'all'}]})
            return new_image_id

        # Launch an instance with base AMI
        try:
            instance_id = AMI.launch_instance_for_tibanna_ami(keyname, userdata_file, base_ami, architecture)
            logger.debug("instance_id=" + instance_id)
        except:
            raise Exception("Failed to launch an instance")

        logger.info("waiting for 10min for the instance to install everything and reboot..")
        time.sleep(10 * 60)

        # Create an image from the instance
        try:
            create_image_args = {'InstanceId': instance_id, 'Name':  ami_name}
            ec2 = boto3.client('ec2')
            logger.info("creating an image...")
            res_create = ec2.create_image(**create_image_args)
        except:
            raise Exception("Failed to create an image")

        logger.info("waiting for 10min for the image to be created..")
        time.sleep(10 * 60)

        # Terminate instance once enough time has passed that we are certain AMI creation
        # should have completed
        try:
            ec2.terminate_instances(InstanceIds=[instance_id])
        except:
            raise Exception("Failed to terminate the instance")

        new_image_id = res_create['ImageId']

        # Make new base image public
        if make_public:
            ec2.modify_image_attribute(ImageId=new_image_id,
                                       LaunchPermission={'Add': [{'Group': 'all'}]})

        # Replicate the image across regions as desired
        if replicate:
            cls.replicate_ami(ami_name=ami_name, ami_id=new_image_id, source_region=base_region,
                              make_public=make_public)

        return new_image_id
