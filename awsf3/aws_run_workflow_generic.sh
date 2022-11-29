#!/bin/bash
shopt -s extglob
export TIBANNA_VERSION=
export AWSF_IMAGE=
export SHUTDOWN_MIN=now
export PASSWORD=
export ACCESS_KEY=
export SECRET_KEY=
export REGION=
export SINGULARITY_OPTION_TO_PASS=
export S3_ENCRYPT_KEY_ID=

printHelpAndExit() {
    echo "Usage: ${0##*/} -i JOBID -l LOGBUCKET -V VERSION -A AWSF_IMAGE [-m SHUTDOWN_MIN] [-p PASSWORD] [-a ACCESS_KEY] [-s SECRET_KEY] [-r REGION] [-g] [-k S3_ENCRYPT_KEY_ID]"
    echo "-i JOBID : awsem job id (required)"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-V TIBANNA_VERSION : tibanna version (used in the run_task lambda that launched this instance)"
    echo "-A AWSF_IMAGE : docker image name for awsf3 (e.g. 4dn-dcic/tibanna-awsf3:1.0.0)"
    echo "-m SHUTDOWN_MIN : Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging. (default 'now')"
    echo "-p PASSWORD : Password for ssh connection for user ec2-user (if not set, no password-based ssh)"
    echo "-a ACCESS_KEY : access key for certain s3 bucket access (if not set, use IAM permission only)"
    echo "-s SECRET_KEY : secret key for certian s3 bucket access (if not set, use IAM permission only)"
    echo "-r REGION : region for the profile set for certain s3 bucket access (if not set, use IAM permission only)"
    echo "-g : use singularity"
    echo "-k S3_ENCRYPT_KEY_ID : KMS key to encrypt s3 files with"
    exit "$1"
}
while getopts "i:m:l:p:a:s:r:gV:A:k:" opt; do
    case $opt in
        i) export JOBID=$OPTARG;;
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        V) export TIBANNA_VERSION=$OPTARG;;  # version of tibanna used in the run_task lambda that launched this instance
        A) export AWSF_IMAGE=$OPTARG;;  # docker image name for awsf3 (e.g. 4dn-dcic/tibanna-awsf3:1.0.0)
        m) export SHUTDOWN_MIN=$OPTARG;;  # Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging.
        p) export PASSWORD=$OPTARG ;;  # Password for ssh connection for user ec2-user
        a) export ACCESS_KEY=$OPTARG;;  # access key for certain s3 bucket access
        s) export SECRET_KEY=$OPTARG;;  # secret key for certian s3 bucket access
        r) export REGION=$OPTARG;;  # region for the profile set for certian s3 bucket access
        g) export SINGULARITY_OPTION_TO_PASS=-g;;  # use singularity
        k) export S3_ENCRYPT_KEY_ID=$OPTARG;;  # KMS key ID to encrypt s3 files with
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

export EBS_DIR=/data1  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_OUTDIR=$EBS_DIR/out
export LOGFILE1=templog___  # log before mounting ebs
export LOGFILE2=$LOCAL_OUTDIR/$JOBID.log
export STATUS=0
export ERRFILE=$LOCAL_OUTDIR/$JOBID.error  # if this is found on s3, that means something went wrong.
export INSTANCE_REGION=$(ec2metadata --availability-zone | sed 's/[a-z]$//')
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity| grep Account | sed 's/[^0-9]//g')


# function that executes a command and collecting log
exl(){ $@ >> $LOGFILE 2>> $LOGFILE; handle_error $?; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong, send error to s3.
exlo(){ $@ 2>> /dev/null >> $LOGFILE; handle_error $?; } ## usage: exlo command  ## ERRCODE has the error code for the command. if something is wrong, send error to s3. This one eats stderr. Useful for hiding long errors or credentials.
exl_no_error(){ $@ >> $LOGFILE 2>> $LOGFILE; } ## same as exl but will not exit on error

# function that sends log to s3 (it requires LOGBUCKET to be defined, which is done by sourcing $ENV_FILE.)
## usage: send_log (no argument)
send_log() {
  if [ -z "$S3_ENCRYPT_KEY_ID" ];
  then
    aws s3 cp $LOGFILE s3://$LOGBUCKET &>/dev/null;
  else
    aws s3 cp $LOGFILE s3://$LOGBUCKET --sse aws:kms --sse-kms-key-id "$S3_ENCRYPT_KEY_ID" &>/dev/null;
  fi
}

# function that sends error file to s3 to notify something went wrong.
## usage: send_error (no argument)
send_error(){
  touch $ERRFILE;
  if [ -z "$S3_ENCRYPT_KEY_ID" ];
  then
    aws s3 cp $ERRFILE s3://$LOGBUCKET;
  else
    aws s3 cp $ERRFILE s3://$LOGBUCKET --sse aws:kms --sse-kms-key-id "$S3_ENCRYPT_KEY_ID";
  fi
}

# function that sends job_started file to s3, notifying that the job successfully started
## usage: send_job_started (no argument)
send_job_started() {
  touch $JOBID.job_started;
  if [ -z "$S3_ENCRYPT_KEY_ID" ];
  then
    aws s3 cp $JOBID.job_started s3://$LOGBUCKET/$JOBID.job_started
  else
    aws s3 cp $JOBID.job_started s3://$LOGBUCKET/$JOBID.job_started --sse aws:kms --sse-kms-key-id "$S3_ENCRYPT_KEY_ID";
  fi
}

# function that handles errors - this function calls send_error and send_log
handle_error() {  ERRCODE=$1; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 ]; then send_error; send_log; shutdown -h $SHUTDOWN_MIN; fi; }  ## usage: handle_error <error_code>

# used to compare Tibanna version strings
version() { echo "$@" | awk -F. '{ printf("%d%03d%03d%03d\n", $1,$2,$3,$4); }'; }

### start with a log under the home directory for ubuntu. Later this will be moved to the output directory, once the ebs is mounted.
export LOGFILE=$LOGFILE1
cd /home/ubuntu/
touch $LOGFILE


# make sure log bucket is defined
if [ -z "$LOGBUCKET" ]; then
    exl echo "Error: log bucket not defined";  # just add this message to the log file, which may help debugging by ssh
    shutdown -h $SHUTDOWN_MIN;
fi
# tibanna version and awsf image should also be defined
if [ -z "$TIBANNA_VERSION" ]; then
    exl echo "Error: tibanna lambda version is not defined";
    handle_error;
fi
if [ -z "$AWSF_IMAGE" ]; then
    exl echo "Error: awsf docker image is not defined";
    handle_error;
fi


### send job start message to S3
send_job_started;

### start logging
### env
exl echo "## Tibanna version: $TIBANNA_VERSION"
exl echo "## job id: $JOBID"
exl echo "## instance type: $(ec2metadata --instance-type)"
exl echo "## instance id: $(ec2metadata --instance-id)"
exl echo "## instance region: $INSTANCE_REGION"
exl echo "## tibanna lambda version: $TIBANNA_VERSION"
exl echo "## awsf image: $AWSF_IMAGE"
exl echo "## ami id: $(ec2metadata --ami-id)"
exl echo "## availability zone: $(ec2metadata --availability-zone)"
exl echo "## security groups: $(ec2metadata --security-groups)"
exl echo "## log bucket: $LOGBUCKET"
exl echo "## shutdown min: $SHUTDOWN_MIN"
exl echo "## kms_key_id: $S3_ENCRYPT_KEY_ID"
exl echo
exl echo "## Starting..."
exl date


### sshd configure for password recognition
exl echo
exl echo "## Configuring and starting ssh"
if [ ! -z $PASSWORD ]; then
  echo -ne "$PASSWORD\n$PASSWORD\n" | sudo passwd ubuntu
  sed 's/PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config | sed 's/#PasswordAuthentication no/PasswordAuthentication yes/g' > tmpp
  mv tmpp /etc/ssh/sshd_config
  exl service ssh restart
fi


###  mount the EBS volume to the EBS_DIR (This has changed and only works with the new ubuntu 20.04 AMI)
exl echo
exl echo "## Mounting EBS"
exl lsblk $TMPLOGFILE
exl export ROOT_EBS=$(lsblk -o PKNAME | tail +2 | awk '$1!=""')
exl export EBS_DEVICE=/dev/$(lsblk -o TYPE,KNAME | tail +2 | grep disk | grep -v $ROOT_EBS | cut -f2 -d' ')
exl mkfs -t ext4 $EBS_DEVICE # creating a file system
exl mkdir /mnt/$EBS_DIR
exl mount $EBS_DEVICE /mnt/$EBS_DIR  # mount
exl ln -s /mnt/$EBS_DIR $EBS_DIR
exl chown -R ubuntu $EBS_DIR
exl chmod -R +x $EBS_DIR
exl echo "Mounting finished."
exl echo "Data EBS file system: $EBS_DEVICE"


### create local outdir under the mounted ebs directory and move log file into that output directory
exl mkdir -p $LOCAL_OUTDIR
mv $LOGFILE1 $LOGFILE2
export LOGFILE=$LOGFILE2


exl echo
exl echo "## Installing and activating Cloudwatch agent to collect metrics"
cwd0=$(pwd)
cd ~

ARCHITECTURE="$(dpkg --print-architecture)"
CW_AGENT_LINK="https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/${ARCHITECTURE}/latest/amazon-cloudwatch-agent.deb"
apt install -y wget
exl echo "Loading Cloudwatch Agent from ${CW_AGENT_LINK}"
wget "${CW_AGENT_LINK}"
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
# If we want to collect new metrics, the following file has to be modified
exl echo "## Using CW Agent config: https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf3/cloudwatch_agent_config.json"
wget https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf3/cloudwatch_agent_config.json
mv ./cloudwatch_agent_config.json /opt/aws/amazon-cloudwatch-agent/bin/config.json
# This starts the agent with the downloaded configuration file
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/bin/config.json

# Set up cronjob to monitor AWS spot instance termination notice.
# Works only in deployed Tibanna version >=1.6.0 since the ec2 needed more permissions to call `aws ec2 describe-spot-instance-requests`
# Since cron only has a resolution of 1 min, we set up 2 jobs and let one sleep for 30s, to get a resolution of 30s.
if [ $(version $TIBANNA_VERSION) -ge $(version "1.6.0") ]; then
  is_spot_instance=`aws ec2 describe-spot-instance-requests --filters Name=instance-id,Values="$(ec2metadata --instance-id)" --region "$INSTANCE_REGION" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['SpotInstanceRequests']))"`
  if [ "$is_spot_instance" = "1" ]; then
    exl echo
    exl echo "## Turning on Spot instance failure detection"
    cd ~
    curl https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf3/spot_failure_detection.sh -O
    chmod +x spot_failure_detection.sh
    if [ -z "$S3_ENCRYPT_KEY_ID" ];
    then
      echo "* * * * * ~/spot_failure_detection.sh -s 0 -l $LOGBUCKET -j $JOBID  >> /var/log/spot_failure_detection.log 2>&1" >> ~/recurring.jobs
      echo "* * * * * ~/spot_failure_detection.sh -s 30 -l $LOGBUCKET -j $JOBID  >> /var/log/spot_failure_detection.log 2>&1" >> ~/recurring.jobs
    else
      echo "* * * * * ~/spot_failure_detection.sh -s 0 -l $LOGBUCKET -j $JOBID -k $S3_ENCRYPT_KEY_ID  >> /var/log/spot_failure_detection.log 2>&1" >> ~/recurring.jobs
      echo "* * * * * ~/spot_failure_detection.sh -s 30 -l $LOGBUCKET -j $JOBID -k $S3_ENCRYPT_KEY_ID  >> /var/log/spot_failure_detection.log 2>&1" >> ~/recurring.jobs
    fi
  fi
fi

# Send the collected jobs to cron
cat ~/recurring.jobs | crontab -

cd $cwd0

# set additional profile
if [ -z $REGION ]; then
  export REGION=$INSTANCE_REGION
fi
if [ ! -z $ACCESS_KEY -a ! -z $SECRET_KEY -a ! -z $REGION ]; then
  echo -ne "$ACCESS_KEY\n$SECRET_KEY\n$REGION\njson" | aws configure --profile user1
fi

### log into ECR if necessary
exl echo
exl echo "## Logging into ECR"
exl echo "Logging into ECR $AWS_ACCOUNT_ID.dkr.ecr.$INSTANCE_REGION.amazonaws.com..."
exlo docker login --username AWS --password $(aws ecr get-login-password --region $INSTANCE_REGION) $AWS_ACCOUNT_ID.dkr.ecr.$INSTANCE_REGION.amazonaws.com;
send_log

# send log before starting docker
exl echo
exl echo "## Running dockerized awsf scripts"
send_log

# run dockerized awsf scripts
# wrap docker pull in some retry logic in case of
# network failures (seen frequently) - Will Sept 22 2021
exl echo "## Pulling Docker image"
tries=0
until [ $tries -ge 3 ]; do
  if exl_no_error docker pull $AWSF_IMAGE; then
    exl echo "## Pull successfull on try $tries"
    break
  else
    ((tries++))
    sleep 60
  fi
done
send_log
# will fail here now if docker pull is not successful after multiple attempts
# pass S3_ENCRYPT_KEY_ID if desired
if [ -z "$S3_ENCRYPT_KEY_ID" ];
then
  docker run --privileged --net host -v /home/ubuntu/:/home/ubuntu/:rw -v /mnt/:/mnt/:rw $AWSF_IMAGE run.sh -i $JOBID -l $LOGBUCKET -f $EBS_DEVICE -S $STATUS $SINGULARITY_OPTION_TO_PASS
else
  docker run --privileged --net host -v /home/ubuntu/:/home/ubuntu/:rw -v /mnt/:/mnt/:rw $AWSF_IMAGE run.sh -i $JOBID -l $LOGBUCKET -f $EBS_DEVICE -S $STATUS $SINGULARITY_OPTION_TO_PASS -k $S3_ENCRYPT_KEY_ID
fi

handle_error $?

### self-terminate
# (option 1)  ## This is the easiest if the 'shutdown behavior' set to 'terminate' for the instance at launch.
shutdown -h $SHUTDOWN_MIN
# (option 2)  ## This works only if the instance is given a proper permission (This is more standard but I never actually got it to work)
#id=$(ec2-metadata -i|cut -d' ' -f2)
#aws ec2 terminate-instances --instance-ids $id
