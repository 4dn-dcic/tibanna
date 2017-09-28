#!/bin/bash
AMAZON_LINUX_AMI_ID=ami-4fffc834
TAG_JSON="ResourceType=instance,Tags=[{Key=Name,Value=tibanna_ami}]"
USER_DATA=file://AMI/tibanna_ami.sh
KEY_NAME=4dn-encode
aws ec2 run-instances --image-id $AMAZON_LINUX_AMI_ID --instance-type t2.micro --count 1 --user-data=$USER_DATA --tag-specifications=$TAG_JSON --key-name=$KEY_NAME
