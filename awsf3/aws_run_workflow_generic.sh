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

printHelpAndExit() {
    echo "Usage: ${0##*/} -i JOBID -l LOGBUCKET -V VERSION -A AWSF_IMAGE [-m SHUTDOWN_MIN] [-p PASSWORD] [-a ACCESS_KEY] [-s SECRET_KEY] [-r REGION] [-g]"
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
    exit "$1"
}
while getopts "i:m:l:p:a:s:r:gV:A:" opt; do
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


# function that executes a command and collecting log
exl(){ $@ >> $LOGFILE 2>> $LOGFILE; handle_error $?; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong, send error to s3.

# function that sends log to s3 (it requires LOGBUCKET to be defined, which is done by sourcing $ENV_FILE.)
send_log(){  aws s3 cp $LOGFILE s3://$LOGBUCKET &>/dev/null; }  ## usage: send_log (no argument)

# function that sends error file to s3 to notify something went wrong.
send_error(){  touch $ERRFILE; aws s3 cp $ERRFILE s3://$LOGBUCKET; }  ## usage: send_error (no argument)

# function that handles errors - this function calls send_error and send_log
handle_error() {  ERRCODE=$1; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 ]; then send_error; send_log; shutdown -h $SHUTDOWN_MIN; fi; }  ## usage: handle_error <error_code>

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
touch $JOBID.job_started
aws s3 cp $JOBID.job_started s3://$LOGBUCKET/$JOBID.job_started

### start logging
### env
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


# set up cronjojb for cloudwatch metrics for memory, disk space and CPU utilization
exl echo
exl echo "## Turning on cloudwatch metrics for memory and disk space"
cwd0=$(pwd)
cd ~
apt install -y unzip libwww-perl libdatetime-perl
curl https://aws-cloudwatch.s3.amazonaws.com/downloads/CloudWatchMonitoringScripts-1.2.2.zip -O
unzip CloudWatchMonitoringScripts-1.2.2.zip && rm CloudWatchMonitoringScripts-1.2.2.zip && cd aws-scripts-mon
echo "*/1 * * * * ~/aws-scripts-mon/mon-put-instance-data.pl --mem-util --mem-used --mem-avail --disk-space-util --disk-space-used --disk-path=/data1/ --from-cron" > cloudwatch.jobs
echo "*/1 * * * * ~/aws-scripts-mon/mon-put-instance-data.pl --disk-space-util --disk-space-used --disk-path=/ --from-cron" >> cloudwatch.jobs
cat cloudwatch.jobs | crontab -
cd $cwd0

# set additional profile
if [ -z $REGION ]; then
  export REGION=$INSTANCE_REGION
fi
if [ ! -z $ACCESS_KEY -a ! -z $SECRET_KEY -a ! -z $REGION ]; then
  echo -ne "$ACCESS_KEY\n$SECRET_KEY\n$REGION\njson" | aws configure --profile user1
fi

# send log before starting docker
exl echo
exl echo "## Running dockerized awsf scripts"
send_log

# run dockerized awsf scripts
docker run --privileged --net host -v /home/ubuntu/:/home/ubuntu/:rw -v /mnt/:/mnt/:rw $AWSF_IMAGE run.sh -i $JOBID -l $LOGBUCKET -f $EBS_DEVICE -S $STATUS $SINGULARITY_OPTION_TO_PASS
handle_error $?

### self-terminate
# (option 1)  ## This is the easiest if the 'shutdown behavior' set to 'terminate' for the instance at launch.
shutdown -h $SHUTDOWN_MIN 
# (option 2)  ## This works only if the instance is given a proper permission (This is more standard but I never actually got it to work)
#id=$(ec2-metadata -i|cut -d' ' -f2)
#aws ec2 terminate-instances --instance-ids $id
