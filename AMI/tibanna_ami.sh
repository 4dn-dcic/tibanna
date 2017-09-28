#!/bin/bash

## installing basic components
yum update -y
yum install -y git gcc

## installing docker
yum install -y docker  # 17.03.2ce-1.59.amzn1 was installed
service docker start
usermod -a -G docker ec2-user  ## to make it work without sudo

## installing python3

# yum install -y epel-release  # already installed on Amazon Linux
yum install -y python35

# Install pip3
yum install -y python35-setuptools  # install easy_install-3.5
easy_install-3.5 pip

# I guess you would like to install virtualenv or virtualenvwrapper
# pip install virtualenv  # already installed on Amazon Linux
pip install virtualenvwrapper


## installing cwl-runner
virtualenv /home/ec2-user/venv/cwl --python=python27
source /home/ec2-user/venv/cwl/bin/activate
pip install --upgrade pip
# pip install cwlref-runner  # doesn't work
cd /home/ec2-user/
git clone https://github.com/SooLee/cwltool
git checkout c7f029e304d1855996218f1c7c12ce1a5c91b8ef
cd cwltool
pip install .
pip install -e git+https://github.com/4dn-dcic/schema_salad#5d6365b3a6246a5a503c341e0043d6456d949769#egg=schema_salad
pip install avro==1.8.2  # 1.8.2 got installed
alias cwl-runner=cwltool

chmod -R 777 /home/ec2-user/

reboot

