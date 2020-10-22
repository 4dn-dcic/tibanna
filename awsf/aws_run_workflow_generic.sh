#!/bin/bash
shopt -s extglob
export SHUTDOWN_MIN=now
export LANGUAGE=cwl_draft3
export PASSWORD=
export ACCESS_KEY=
export SECRET_KEY=
export REGION=
export SINGULARITY_OPTION=
export TIBANNA_VERSION=

printHelpAndExit() {
    echo "Usage: ${0##*/} -i JOBID [-m SHUTDOWN_MIN] -j JSON_BUCKET_NAME -l LOGBUCKET [-u SCRIPTS_URL] [-p PASSWORD] [-a ACCESS_KEY] [-s SECRET_KEY] [-r REGION] [-g] [-V VERSION]"
    echo "-i JOBID : awsem job id (required)"
    echo "-m SHUTDOWN_MIN : Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging. (default 'now')"
    echo "-j JSON_BUCKET_NAME : bucket for sending run.json file. This script gets run.json file from this bucket. e.g.: 4dn-aws-pipeline-run-json (required)"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-L LANGUAGE : workflow language ('cwl_draft3', 'cwl_v1', 'wdl', 'snakemake', or 'shell') (default cwl_draft3)"
    echo "-p PASSWORD : Password for ssh connection for user ec2-user (if not set, no password-based ssh)"
    echo "-a ACCESS_KEY : access key for certain s3 bucket access (if not set, use IAM permission only)"
    echo "-s SECRET_KEY : secret key for certian s3 bucket access (if not set, use IAM permission only)"
    echo "-r REGION : region for the profile set for certain s3 bucket access (if not set, use IAM permission only)"
    echo "-g : use singularity"
    echo "-V TIBANNA_VERSION : tibanna version (used in the run_task lambda that launched this instance)"
    exit "$1"
}
while getopts "i:m:j:l:L:u:p:a:s:r:gV:" opt; do
    case $opt in
        i) export JOBID=$OPTARG;;
        m) export SHUTDOWN_MIN=$OPTARG;;  # Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging.
        j) export JSON_BUCKET_NAME=$OPTARG;;  # bucket for sending run.json file. This script gets run.json file from this bucket. e.g.: 4dn-aws-pipeline-run-json
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        L) export LANGUAGE=$OPTARG;;  # workflow language
        p) export PASSWORD=$OPTARG ;;  # Password for ssh connection for user ec2-user
        a) export ACCESS_KEY=$OPTARG;;  # access key for certain s3 bucket access
        s) export SECRET_KEY=$OPTARG;;  # secret key for certian s3 bucket access
        r) export REGION=$OPTARG;;  # region for the profile set for certian s3 bucket access
        g) export SINGULARITY_OPTION=--singularity;;  # use singularity
        V) export TIBANNA_VERSION=$OPTARG;;  # version of tibanna used in the run_task lambda that launched this instance
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

export RUN_JSON_FILE_NAME=$JOBID.run.json
export POSTRUN_JSON_FILE_NAME=$JOBID.postrun.json
export EBS_DIR=/data1  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_OUTDIR=$EBS_DIR/out  
export LOCAL_INPUT_DIR=$EBS_DIR/input  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_REFERENCE_DIR=$EBS_DIR/reference  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_WF_TMPDIR=$EBS_DIR/tmp
export MD5FILE=$JOBID.md5sum.txt
export INPUT_YML_FILE=inputs.yml
export DOWNLOAD_COMMAND_FILE=download_command_list.txt
export MOUNT_COMMAND_FILE=mount_command_list.txt
export ENV_FILE=env_command_list.txt
export LOGFILE1=templog___  # log before mounting ebs
export LOGFILE2=$LOCAL_OUTDIR/$JOBID.log
export LOGJSONFILE=$LOCAL_OUTDIR/$JOBID.log.json
export STATUS=0
export ERRFILE=$LOCAL_OUTDIR/$JOBID.error  # if this is found on s3, that means something went wrong.
export INSTANCE_ID=$(ec2metadata --instance-id|cut -d' ' -f2)
export INSTANCE_REGION=$(ec2metadata --availability-zone | sed 's/[a-z]$//')

if [[ $LANGUAGE == 'wdl' ]]
then
  export LOCAL_WFDIR=$EBS_DIR/wdl
elif [[ $LANGUAGE == 'snakemake' ]]
then
  export LOCAL_WFDIR=$EBS_DIR/snakemake
elif [[ $LANGUAGE == 'shell' ]]
then
  export LOCAL_WFDIR=$EBS_DIR/shell
else
  export LOCAL_WFDIR=$EBS_DIR/cwl
fi

# set profile
echo -ne "$ACCESS_KEY\n$SECRET_KEY\n$REGION\njson" | aws configure --profile user1

# first create an output bucket/directory
touch $JOBID.job_started
aws s3 cp $JOBID.job_started s3://$LOGBUCKET/$JOBID.job_started

# function that executes a command and collecting log
exl(){ $@ >> $LOGFILE 2>> $LOGFILE; ERRCODE=$?; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 -a ! -z "$LOGBUCKET" ]; then send_error; fi; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong and if LOGBUCKET has already been defined, send error to s3.
exlj(){ $@ >> $LOGJSONFILE 2>> $LOGFILE; ERRCODE=$?; cat $LOGJSONFILE >> $LOGFILE; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 -a ! -z "$LOGBUCKET" ]; then send_error; fi; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong and if LOGBUCKET has already been defined, send error to s3. This one separates stdout to json as well.
exle(){ $@ >> /dev/null 2>> $LOGFILE; ERRCODE=$?; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 -a ! -z "$LOGBUCKET" ]; then send_error; fi; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong and if LOGBUCKET has already been defined, send error to s3. This one eats stdout. Useful for downloading/uploading files to/from s3, because it writes progress to stdout.


# function that sends log to s3 (it requires LOGBUCKET to be defined, which is done by sourcing $ENV_FILE.)
send_log(){  aws s3 cp $LOGFILE s3://$LOGBUCKET; }  ## usage: send_log (no argument)
send_log_regularly(){  
    watch -n 60 "top -b | head -15 >> $LOGFILE; \
    du -h $LOCAL_INPUT_DIR/ >> $LOGFILE; \
    du -h $LOCAL_WF_TMPDIR*/ >> $LOGFILE; \
    du -h $LOCAL_OUTDIR/ >> $LOGFILE; \
    aws s3 cp $LOGFILE s3://$LOGBUCKET &>/dev/null";
}  ## usage: send_log_regularly (no argument)

# function that sends error file to s3 to notify something went wrong.
send_error(){  touch $ERRFILE; aws s3 cp $ERRFILE s3://$LOGBUCKET; }  ## usage: send_log (no argument)


### start with a log under the home directory for ubuntu. Later this will be moved to the output directory, once the ebs is mounted.
LOGFILE=$LOGFILE1
cd /home/ubuntu/
touch $LOGFILE 
exl date  ## start logging


### sshd configure for password recognition
if [ ! -z $PASSWORD ]; then
  echo -ne "$PASSWORD\n$PASSWORD\n" | sudo passwd ubuntu
  sed 's/PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config | sed 's/#PasswordAuthentication no/PasswordAuthentication yes/g' > tmpp
  mv tmpp /etc/ssh/sshd_config
  exl service ssh restart
fi


###  mount the EBS volume to the EBS_DIR
exl lsblk $TMPLOGFILE
export EBS_DEVICE=/dev/$(lsblk | tail -1 | cut -f1 -d' ')
exl mkfs -t ext4 $EBS_DEVICE # creating a file system
exl mkdir /mnt/$EBS_DIR
exl mount $EBS_DEVICE /mnt/$EBS_DIR  # mount
exl ln -s /mnt/$EBS_DIR $EBS_DIR
exl chown -R ubuntu $EBS_DIR
exl chmod -R +x $EBS_DIR


# set up cronjojb for cloudwatch metrics for memory, disk space and CPU utilization
cwd0=$(pwd)
cd ~
apt-get update
apt-get install -y unzip libwww-perl libdatetime-perl
curl https://aws-cloudwatch.s3.amazonaws.com/downloads/CloudWatchMonitoringScripts-1.2.2.zip -O
unzip CloudWatchMonitoringScripts-1.2.2.zip && rm CloudWatchMonitoringScripts-1.2.2.zip && cd aws-scripts-mon
echo "*/1 * * * * ~/aws-scripts-mon/mon-put-instance-data.pl --mem-util --mem-used --mem-avail --disk-space-util --disk-space-used --disk-path=/data1/ --from-cron" > cloudwatch.jobs
echo "*/1 * * * * ~/aws-scripts-mon/mon-put-instance-data.pl --disk-space-util --disk-space-used --disk-path=/ --from-cron" >> cloudwatch.jobs
cat cloudwatch.jobs | crontab -
cd $cwd0


# run dockerized awsf scripts
docker run --privileged --net host -it -v /home/ubuntu/:/home/ubuntu/:rw -v /mnt/:/mnt/:rw duplexa/tibanna-awsf:pre aws_run_workflow_generic.sh -i $JOBID -j $JSON_BUCKET_NAME -l $LOGBUCKET -L $LANGUAGE-V $TIBANNA_VERSION -R $INSTANCE_REGION


### self-terminate
# (option 1)  ## This is the easiest if the 'shutdown behavior' set to 'terminate' for the instance at launch.
sudo shutdown -h $SHUTDOWN_MIN 
# (option 2)  ## This works only if the instance is given a proper permission (This is more standard but I never actually got it to work)
#id=$(ec2-metadata -i|cut -d' ' -f2)
#aws ec2 terminate-instances --instance-ids $id
