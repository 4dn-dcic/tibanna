#!/bin/bash
shopt -s extglob
export SINGULARITY_OPTION=
export STATUS=0
export LOGBUCKET=

printHelpAndExit() {
    echo "Usage: ${0##*/} -i JOBID -l LOGBUCKET -f EBS_DEVICE [-S STATUS] [-g]"
    echo "-i JOBID : awsem job id (required)"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-f EBS_DEVICE : file system (/dev/xxxx) for data EBS"
    echo "-S STATUS: inherited status environment variable, if any"
    echo "-g : use singularity"
    exit "$1"
}
while getopts "i:l:f:S:g" opt; do
    case $opt in
        i) export JOBID=$OPTARG;;
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        f) export EBS_DEVICE=$OPTARG;;  # file system (/dev/xxxx) for data EBS
        S) export STATUS=$OPTARG;;  # inherited STATUS env
        g) export SINGULARITY_OPTION=--singularity;;  # use singularity
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

export RUN_JSON_FILE_NAME=$JOBID.run.json
export POSTRUN_JSON_FILE_NAME=$JOBID.postrun.json
export EBS_DIR=/data1  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_OUTDIR=$EBS_DIR/out  
export LOCAL_INPUT_DIR=$EBS_DIR/input  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_WF_TMPDIR=$EBS_DIR/tmp
export MD5FILE=$JOBID.md5sum.txt
export INPUT_YML_FILE=inputs.yml
export DOWNLOAD_COMMAND_FILE=download_command_list.txt
export MOUNT_COMMAND_FILE=mount_command_list.txt
export ENV_FILE=env_command_list.txt
export LOGFILE=$LOCAL_OUTDIR/$JOBID.log
export LOGJSONFILE=$LOCAL_OUTDIR/$JOBID.log.json
export ERRFILE=$LOCAL_OUTDIR/$JOBID.error  # if this is found on s3, that means something went wrong.
export TOPFILE=$LOCAL_OUTDIR/$JOBID.top  # now top command output goes to a separate file
export TOPLATESTFILE=$LOCAL_OUTDIR/$JOBID.top_latest  # this one includes only the latest top command output
export INSTANCE_ID=$(ec2metadata --instance-id|cut -d' ' -f2)
export INSTANCE_REGION=$(ec2metadata --availability-zone | sed 's/[a-z]$//')
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity| grep Account | sed 's/[^0-9]//g')
export AWS_REGION=$INSTANCE_REGION  # this is for importing awsf3 package which imports tibanna package

# function that executes a command and collecting log
exl(){ $@ >> $LOGFILE 2>> $LOGFILE; handle_error $?; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong, send error to s3.
exlj(){ $@ >> $LOGJSONFILE 2>> $LOGFILE; $ERRCODE=$?; cat $LOGJSONFILE >> $LOGFILE; handle_error $ERRCODE; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong, send error to s3. This one separates stdout to json as well.
exle(){ $@ >> /dev/null 2>> $LOGFILE; handle_error $?; } ## usage: exle command  ## ERRCODE has the error code for the command. if something is wrong, send error to s3. This one eats stdout. Useful for downloading/uploading files to/from s3, because it writes progress to stdout.
exlo(){ $@ 2>> /dev/null >> $LOGFILE; handle_error $?; } ## usage: exlo command  ## ERRCODE has the error code for the command. if something is wrong, send error to s3. This one eats stderr. Useful for hiding long errors or credentials.

# function that sends log to s3 (it requires LOGBUCKET to be defined, which is done by sourcing $ENV_FILE.)
send_log(){  aws s3 cp $LOGFILE s3://$LOGBUCKET &>/dev/null; }  ## usage: send_log (no argument)

# function that sends error file to s3 to notify something went wrong.
send_error(){  touch $ERRFILE; aws s3 cp $ERRFILE s3://$LOGBUCKET; }  ## usage: send_error (no argument)

# function that handles errors - this function calls send_error and send_log
handle_error() {  ERRCODE=$1; export STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 ]; then send_error; send_log; exit $ERRCODE; fi; }  ## usage: handle_error <error_code>


# make sure log bucket is defined
if [ -z "$LOGBUCKET" ]; then
    exl echo "Error: log bucket not defined"
    send_error 1;
fi


# EBS_DIR cannot be directly mounted to docker container since it's already a mount point for EBS,
# so mount /mnt/data1/ instead and create a symlink.
ln -s /mnt/$EBS_DIR $EBS_DIR

# Transferring profile info
ln -s /home/ubuntu/.aws /root/.aws

# log the first message from the container
exl echo
exl echo "## AWSF Docker container created"
exl echo "## instance id: $INSTANCE_ID"
exl echo "## instance region: $INSTANCE_REGION"

# docker start
exl echo
exl echo "## Starting docker in the AWSF container"
exl service docker start


# versions of various tools
exl echo
exl echo "## $(docker --version)"
exl echo "## $(python --version)"
exl echo "## $(pip --version | cut -f1,2 -d' ')"
exl echo "## tibanna awsf3 version $(tibanna --version | cut -f2 -d' ')"
exl echo "## cwltool version $(cwltool --version | cut -f2 -d' ')"
exl echo "## cromwell version $(java -jar /usr/local/bin/cromwell.jar --version | cut -f2 -d ' ')"
exl echo "## $(singularity --version)"


# getting run.json file
exl echo
exl echo "## Downloading and parsing run.json file"
exl cd /home/ubuntu/
exl aws s3 cp s3://$LOGBUCKET/$RUN_JSON_FILE_NAME .
exl chmod -R +x .
exl awsf3 decode_run_json -i $RUN_JSON_FILE_NAME


### add instance ID and file system to postrun json and upload to s3
exl awsf3 update_postrun_json_init -i $RUN_JSON_FILE_NAME -o $POSTRUN_JSON_FILE_NAME
exl awsf3 upload_postrun_json -i $POSTRUN_JSON_FILE_NAME


# setting additional env variables including LANGUAGE and language-related envs.
exl source $ENV_FILE


# create subdirectories
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
exl mkdir -p $LOCAL_WFDIR
send_log


### download cwl from github or any other url.
exl echo
exl echo "## Downloading workflow files"
exl awsf3 download_workflow


### log into ECR if necessary
exl echo
exl echo "## Logging into ECR"
exlo docker login --username AWS --password $(aws ecr get-login-password --region $INSTANCE_REGION) $AWS_ACCOUNT_ID.dkr.ecr.$INSTANCE_REGION.amazonaws.com;
send_log


### download data & reference files from s3
exl echo
exl echo "## Downloading data & reference files from S3"
exl date 
exl mkdir -p $LOCAL_INPUT_DIR
exl cat $DOWNLOAD_COMMAND_FILE
exle source $DOWNLOAD_COMMAND_FILE 
exl date
send_log 


### mount input buckets
exl echo
exl echo "## Mounting input S3 buckets"
exl cat $MOUNT_COMMAND_FILE
exle source $MOUNT_COMMAND_FILE
send_log


### just some more logging
exl echo
exl echo "## Current file system status"
exl df -h
exl echo
exl ls -lh $EBS_DIR
exl echo
exl ls -lhR $LOCAL_INPUT_DIR
send_log


# set up cronjob for top command
exl echo
exl echo "## Setting up and starting cron job for top commands"
exl service cron start
echo "*/1 * * * * /usr/local/bin/cron.sh -l $LOGBUCKET -L $LOGFILE -t $TOPFILE -T $TOPLATESTFILE" | crontab -


### run command
exl echo
exl echo "## Running CWL/WDL/Snakemake/Shell commands"
exl echo
exl echo "## workflow language: $LANGUAGE"
exl echo "## $(docker info | grep 'Operating System')"
exl echo "## $(docker info | grep 'Docker Root Dir')"
exl echo "## $(docker info | grep 'CPUs')"
exl echo "## $(docker info | grep 'Total Memory')"
exl echo
send_log
cwd0=$(pwd)
cd $LOCAL_WFDIR  
mkdir -p $LOCAL_WF_TMPDIR
if [[ $LANGUAGE == 'wdl' ]]
then
  exl java -jar /usr/local/bin/cromwell.jar run $MAIN_WDL -i $cwd0/$INPUT_YML_FILE -m $LOGJSONFILE
  handle_error $?
elif [[ $LANGUAGE == 'snakemake' ]]
then
  exl echo "running $COMMAND in docker image $CONTAINER_IMAGE..."
  docker run --privileged -v $EBS_DIR:$EBS_DIR:rw -w $LOCAL_WFDIR $DOCKER_ENV_OPTION $CONTAINER_IMAGE sh -c "$COMMAND" >> $LOGFILE 2>> $LOGFILE;
  handle_error $?
elif [[ $LANGUAGE == 'shell' ]]
then
  exl echo "running $COMMAND in docker image $CONTAINER_IMAGE..."
  exl echo "docker run --privileged -v $EBS_DIR:$EBS_DIR:rw -w $LOCAL_WFDIR $DOCKER_ENV_OPTION $CONTAINER_IMAGE sh -c \"$COMMAND\""
  docker run --privileged -v $EBS_DIR:$EBS_DIR:rw -w $LOCAL_WFDIR $DOCKER_ENV_OPTION $CONTAINER_IMAGE sh -c "$COMMAND" >> $LOGFILE 2>> $LOGFILE;
  handle_error $?
else
  if [[ $LANGUAGE == 'cwl_draft3' ]]
  then
    # older version of cwltool that works with draft3
    exl echo
    exl echo "## switching to an older version of cwltool that supports draft3"
    pip uninstall -y cwltool
    git clone https://github.com/SooLee/cwltool
    cd cwltool
    exl git checkout c7f029e304d1855996218f1c7c12ce1a5c91b8ef
    python setup.py install
    cd $LOCAL_WFDIR
  fi
  exlj cwltool --enable-dev --non-strict --no-read-only --no-match-user --outdir $LOCAL_OUTDIR --tmp-outdir-prefix $LOCAL_WF_TMPDIR --tmpdir-prefix $LOCAL_WF_TMPDIR $PRESERVED_ENV_OPTION $SINGULARITY_OPTION $MAIN_CWL $cwd0/$INPUT_YML_FILE
  handle_error $?
fi
cd $cwd0
exl echo
exl echo "Finished running the command/workflow"
send_log 

### copy output files to s3
exl echo
exl echo "## Calculating md5sum of output files"
exl date
md5sum $LOCAL_OUTDIR/* | grep -v "$JOBID" >> $MD5FILE ;  ## calculate md5sum for output files (except log file, to avoid confusion)
exl cat $MD5FILE
mv $MD5FILE $LOCAL_OUTDIR
exl date ## done time
send_log

exl echo
exl echo "## Current file system status"
exl df -h
exl echo
exl ls -lhtrR $LOCAL_OUTDIR/
exl echo
exl ls -lhtr $EBS_DIR/
exl echo
exl ls -lhtrR $LOCAL_INPUT_DIR/
send_log

# more comprehensive log for wdl
if [[ $LANGUAGE == 'wdl' ]]
then
  exl echo
  exl echo "## Uploading WDL log files to S3"
  cwd0=$(pwd)
  cd $LOCAL_WFDIR
  find . -type f -name 'stdout' -or -name 'stderr' -or -name 'script' -or \
-name '*.qc' -or -name '*.txt' -or -name '*.log' -or -name '*.png' -or -name '*.pdf' \
| xargs tar -zcvf debug.tar.gz
  exle aws s3 cp debug.tar.gz s3://$LOGBUCKET/$JOBID.debug.tar.gz
  cd $cwd0
fi

exl echo
exl echo "## Uploading output files to S3"
if [[ $LANGUAGE == 'snakemake' || $LANGUAGE == 'shell' ]]
then
    # no log json file is produced
    export LOGJSON_OPTION=
else
    export LOGJSON_OPTION="-e $LOGJSONFILE"
fi
exl awsf3 update_postrun_json_upload_output -i $POSTRUN_JSON_FILE_NAME $LOGJSON_OPTION -m $LOCAL_OUTDIR/$MD5FILE -o $POSTRUN_JSON_FILE_NAME -L $LANGUAGE
exl awsf3 upload_postrun_json -i $POSTRUN_JSON_FILE_NAME
send_log
 
### updating status
exl echo
exl echo "## Checking the job status (0 means success)"
## if STATUS is 21,0,0,1 JOB_STATUS is 21,0,0,1. If STATUS is 0,0,0,0,0,0, JOB_STATUS is 0.
if [ $(echo $STATUS| sed 's/0//g' | sed 's/,//g') ]; then export JOB_STATUS=$STATUS ; else export JOB_STATUS=0; fi
exl echo "JOB_STATUS=$JOB_STATUS"
# This env variable (JOB_STATUS) will be read by aws_update_run_json.py and the result will go into $POSTRUN_JSON_FILE_NAME. 

# update & upload postrun json
exl echo
exl echo "## Updating postrun json file with status, time stamp, input & output size"
# create a postrun.json file that contains the information in the run.json file and additional information (status, stop_time)
export INPUTSIZE=$(du -csh /data1/input| tail -1 | cut -f1)
export TEMPSIZE=$(du -csh /data1/tmp*| tail -1 | cut -f1)
export OUTPUTSIZE=$(du -csh /data1/out| tail -1 | cut -f1)
exl awsf3 update_postrun_json_final -i $POSTRUN_JSON_FILE_NAME -o $POSTRUN_JSON_FILE_NAME -l $LOGFILE
exl awsf3 upload_postrun_json -i $POSTRUN_JSON_FILE_NAME

# send the final log
exl echo
exl echo "Done"
exl date
send_log

# send success message
if [ ! -z $JOB_STATUS -a $JOB_STATUS == 0 ]; then touch $JOBID.success; aws s3 cp $JOBID.success s3://$LOGBUCKET/; fi
