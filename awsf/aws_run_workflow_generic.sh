#!/bin/bash
shopt -s extglob
export SHUTDOWN_MIN=now
export SCRIPTS_URL=https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/
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
    echo "-u SCRIPTS_URL : Tibanna repo url (default: https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/)"
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
        u) export SCRIPTS_URL=$OPTARG;;  # Tibanna repo url (e.g. https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/)
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
export INSTANCE_ID=$(ec2metadata -i|cut -d' ' -f2)
export INSTANCE_REGION=$(ec2metadata --availability-zone | sed 's/[a-z]$//')
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity| grep Account | sed 's/[^0-9]//g')

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
-echo -ne "$PASSWORD\n$PASSWORD\n" | passwd ubuntu
-sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config
-exl service ssh restart

### sshd configure for password recognition
if [ ! -z $PASSWORD ]; then
  echo -ne "$PASSWORD\n$PASSWORD\n" | sudo passwd ubuntu
  sed 's/PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config | sed 's/#PasswordAuthentication no/PasswordAuthentication yes/g' > tmpp
  mv tmpp /etc/ssh/sshd_config
  exl service ssh restart
fi


### 2. get the run.json file and parse it to get environmental variables WDL_URL, MAIN_WDL, and LOGBUCKET and create an inputs.yml file (INPUT_YML_FILE).
exl wget $SCRIPTS_URL/aws_decode_run_json.py
exl wget $SCRIPTS_URL/aws_update_run_json.py
exl wget $SCRIPTS_URL/aws_upload_output_update_json.py
exl wget $SCRIPTS_URL/download_workflow.py

exl echo $JSON_BUCKET_NAME
exl aws s3 cp s3://$JSON_BUCKET_NAME/$RUN_JSON_FILE_NAME .
exl chown -R ubuntu .
exl chmod -R +x .
exl ./aws_decode_run_json.py $RUN_JSON_FILE_NAME
exl source $ENV_FILE

###  mount the EBS volume to the EBS_DIR
exl lsblk $TMPLOGFILE
export EBS_DEVICE=/dev/$(lsblk | tail -1 | cut -f1 -d' ')
exl mkfs -t ext4 $EBS_DEVICE # creating a file system
exl mkdir $EBS_DIR
exl mount $EBS_DEVICE $EBS_DIR # mount
exl chown -R ubuntu $EBS_DIR
exl chmod -R +x $EBS_DIR


### create subdirectories under the mounted ebs directory and move log file into that output directory
exl mkdir -p $LOCAL_OUTDIR
exl mkdir -p $LOCAL_INPUT_DIR
exl mkdir -p $LOCAL_REFERENCE_DIR
exl mkdir -p $LOCAL_WFDIR
mv $LOGFILE1 $LOGFILE2
LOGFILE=$LOGFILE2
send_log

### download cwl from github or any other url.
pip install boto3
exl ./download_workflow.py

# set up cronjojb for cloudwatch metrics for memory, disk space and CPU utilization
cwd0=$(pwd)
cd ~
apt-get update
apt-get install -y unzip libwww-perl libdatetime-perl
curl https://aws-cloudwatch.s3.amazonaws.com/downloads/CloudWatchMonitoringScripts-1.2.2.zip -O
unzip CloudWatchMonitoringScripts-1.2.2.zip && rm CloudWatchMonitoringScripts-1.2.2.zip && cd aws-scripts-mon
echo "*/1 * * * * ~/aws-scripts-mon/mon-put-instance-data.pl --mem-util --mem-used --mem-avail --disk-space-util --disk-space-used --disk-path=/data1/ --from-cron" > cloudwatch.jobs
echo "*/1 * * * * ~/aws-scripts-mon/mon-put-instance-data.pl --disk-space-util --disk-space-used --disk-path=/ --from-cron" >> cloudwatch.jobs
echo "*/1 * * * * top -b | head -15 >> $LOGFILE; du -h $LOCAL_INPUT_DIR/ >> $LOGFILE; du -h $LOCAL_WF_TMPDIR*/ >> $LOGFILE; du -h $LOCAL_OUTDIR/ >> $LOGFILE; aws s3 cp $LOGFILE s3://$LOGBUCKET &>/dev/null" >> cloudwatch.jobs
cat cloudwatch.jobs | crontab -
cd $cwd0

### prepare for file mounting
exl curl -O -L http://bit.ly/goofys-latest
exl chmod +x goofys-latest
exl echo "user_allow_other" >> /etc/fuse.conf
export GOOFYS_COMMAND='./goofys-latest -o allow_other -o nonempty'

### log into ECR if necessary
if [[ ! -z "$TIBANNA_VERSION" && "$TIBANNA_VERSION" > '0.18' ]]; then
  pip install awscli -U;
  exl docker login --username AWS --password $(aws ecr get-login-password --region $INSTANCE_REGION) $AWS_ACCOUNT_ID.dkr.ecr.$INSTANCE_REGION.amazonaws.com;
fi

### urllib3 version conflict
pip uninstall -y urllib3
pip install urllib3==1.21.1

### download data & reference files from s3
exl cat $DOWNLOAD_COMMAND_FILE
exl date 
exle source $DOWNLOAD_COMMAND_FILE 
exl date
exl ls
send_log 

### mount input buckets
exl cat $MOUNT_COMMAND_FILE
exl date
exle source $MOUNT_COMMAND_FILE
exl date
exl ls
send_log

### just some more logging
exl df
exl pwd
exl ls -lh /
exl ls -lh $EBS_DIR
exl ls -lhR $LOCAL_INPUT_DIR
exl ls -lhR $LOCAL_WFDIR
send_log

### run command
cwd0=$(pwd)
cd $LOCAL_WFDIR  
mkdir -p $LOCAL_WF_TMPDIR
#send_log_regularly &
if [[ $LANGUAGE == 'wdl' ]]
then
  exl java -jar ~ubuntu/cromwell/cromwell.jar run $MAIN_WDL -i $cwd0/$INPUT_YML_FILE -m $LOGJSONFILE
elif [[ $LANGUAGE == 'snakemake' ]]
then
  exl echo "running $COMMAND in docker image $CONTAINER_IMAGE..."
  docker run --privileged -v $EBS_DIR:$EBS_DIR:rw -w $LOCAL_WFDIR $DOCKER_ENV_OPTION $CONTAINER_IMAGE sh -c "$COMMAND" >> $LOGFILE 2>> $LOGFILE; ERRCODE=$?; STATUS+=,$ERRCODE;
  if [ "$ERRCODE" -ne 0 -a ! -z "$LOGBUCKET" ]; then send_error; fi;
  LOGJSONFILE='-'  # no file
elif [[ $LANGUAGE == 'shell' ]]
then
  exl echo "running $COMMAND in docker image $CONTAINER_IMAGE..."
  exl echo "docker run --privileged -v $EBS_DIR:$EBS_DIR:rw -w $LOCAL_WFDIR $DOCKER_ENV_OPTION $CONTAINER_IMAGE sh -c \"$COMMAND\""
  docker run --privileged -v $EBS_DIR:$EBS_DIR:rw -w $LOCAL_WFDIR $DOCKER_ENV_OPTION $CONTAINER_IMAGE sh -c "$COMMAND" >> $LOGFILE 2>> $LOGFILE; ERRCODE=$?; STATUS+=,$ERRCODE;
  if [ "$ERRCODE" -ne 0 -a ! -z "$LOGBUCKET" ]; then send_error; fi;
  LOGJSONFILE='-'  # no file
else
  if [[ $LANGUAGE == 'cwl_draft3' ]]
  then
    # older version of cwltoolthat works with draft3
    pip uninstall cwltool
    git clone https://github.com/SooLee/cwltool
    cd cwltool
    git checkout c7f029e304d1855996218f1c7c12ce1a5c91b8ef
    python setup.py install
    cd $LOCAL_WFDIR
  fi
  exlj cwltool --enable-dev --non-strict --no-read-only --no-match-user --outdir $LOCAL_OUTDIR --tmp-outdir-prefix $LOCAL_WF_TMPDIR --tmpdir-prefix $LOCAL_WF_TMPDIR $PRESERVED_ENV_OPTION $SINGULARITY_OPTION $MAIN_CWL $cwd0/$INPUT_YML_FILE
fi
cd $cwd0
send_log 

### copy output files to s3
md5sum $LOCAL_OUTDIR/* | grep -v "$LOGFILE" >> $MD5FILE ;  ## calculate md5sum for output files (except log file, to avoid confusion)
mv $MD5FILE $LOCAL_OUTDIR
exl date ## done time
send_log
exl ls -lhtrR $LOCAL_OUTDIR/
exl ls -lhtr $EBS_DIR/
exl ls -lhtrR $LOCAL_INPUT_DIR/
exl ls -lhtrR $LOCAL_WFDIR/
#exle aws s3 cp --recursive $LOCAL_OUTDIR s3://$OUTBUCKET
if [[ $LANGUAGE == 'wdl' ]]
then
  LANGUAGE_OPTION=wdl
elif [[ $LANGUAGE == 'snakemake' ]]
then
  LANGUAGE_OPTION=snakemake
elif [[ $LANGUAGE == 'shell' ]]
then
  LANGUAGE_OPTION=shell
else
  LANGUAGE_OPTION=
fi
exle ./aws_upload_output_update_json.py $RUN_JSON_FILE_NAME $LOGJSONFILE $LOGFILE $LOCAL_OUTDIR/$MD5FILE $POSTRUN_JSON_FILE_NAME $LANGUAGE_OPTION
mv $POSTRUN_JSON_FILE_NAME $RUN_JSON_FILE_NAME
send_log
 
### updating status
# status report should be improved.
if [ $(echo $STATUS| sed 's/0//g' | sed 's/,//g') ]; then export JOB_STATUS=$STATUS ; else export JOB_STATUS=0; fi ## if STATUS is 21,0,0,1 JOB_STATUS is 21,0,0,1. If STATUS is 0,0,0,0,0,0, JOB_STATUS is 0.
# This env variable (JOB_STATUS) will be read by aws_update_run_json.py and the result will go into $POSTRUN_JSON_FILE_NAME. 
### 8. create a postrun.json file that contains the information in the run.json file and additional information (status, stop_time)
export INPUTSIZE=$(du -csh /data1/input| tail -1 | cut -f1)
export TEMPSIZE=$(du -csh /data1/tmp*| tail -1 | cut -f1)
export OUTPUTSIZE=$(du -csh /data1/out| tail -1 | cut -f1)

exl ./aws_update_run_json.py $RUN_JSON_FILE_NAME $POSTRUN_JSON_FILE_NAME
if [[ $PUBLIC_POSTRUN_JSON == '1' ]]
then
  exle aws s3 cp $POSTRUN_JSON_FILE_NAME s3://$LOGBUCKET/$POSTRUN_JSON_FILE_NAME --acl public-read
else
  exle aws s3 cp $POSTRUN_JSON_FILE_NAME s3://$LOGBUCKET/$POSTRUN_JSON_FILE_NAME
fi
if [ ! -z $JOB_STATUS -a $JOB_STATUS == 0 ]; then touch $JOBID.success; aws s3 cp $JOBID.success s3://$LOGBUCKET/; fi
send_log

df -h >> $LOGFILE
send_log


# more comprehensive log for wdl
if [[ $LANGUAGE == 'wdl' ]]
then
  cd $LOCAL_WFDIR
  find . -type f -name 'stdout' -or -name 'stderr' -or -name 'script' -or \
-name '*.qc' -or -name '*.txt' -or -name '*.log' -or -name '*.png' -or -name '*.pdf' \
| xargs tar -zcvf debug.tar.gz
  aws s3 cp debug.tar.gz s3://$LOGBUCKET/$JOBID.debug.tar.gz
fi

### how do we send a signal that the job finished?
#<some script>
 
### self-terminate
# (option 1)  ## This is the easiest if the 'shutdown behavior' set to 'terminate' for the instance at launch.
sudo shutdown -h $SHUTDOWN_MIN 
# (option 2)  ## This works only if the instance is given a proper permission (This is more standard but I never actually got it to work)
#id=$(ec2-metadata -i|cut -d' ' -f2)
#aws ec2 terminate-instances --instance-ids $id
