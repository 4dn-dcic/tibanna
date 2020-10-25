#!/bin/bash
shopt -s extglob
export INSTANCE_REGION=
export INSTANCE_ID=
export LANGUAGE=cwl_draft3
export ACCESS_KEY=
export SECRET_KEY=
export REGION=
export SINGULARITY_OPTION=
export TIBANNA_VERSION=
export STATUS=0

printHelpAndExit() {
    echo "Usage: ${0##*/} -i JOBID -R INSTANCE_REGION -I INSTANCE_ID -j JSON_BUCKET_NAME -l LOGBUCKET [-S STATUS] [-a ACCESS_KEY] [-s SECRET_KEY] [-r REGION] [-g] [-V VERSION]"
    echo "-i JOBID : awsem job id (required)"
    echo "-R INSTANCE_REGION: region of the current EC2 instance (required)"
    echo "-I INSTANCE_ID: ID of the current EC2 instance (required)"
    echo "-j JSON_BUCKET_NAME : bucket for sending run.json file. This script gets run.json file from this bucket. e.g.: 4dn-aws-pipeline-run-json (required)"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-S STATUS: inherited status environment variable, if any"
    echo "-L LANGUAGE : workflow language ('cwl_draft3', 'cwl_v1', 'wdl', 'snakemake', or 'shell') (default cwl_draft3)"
    echo "-a ACCESS_KEY : access key for certain s3 bucket access (if not set, use IAM permission only)"
    echo "-s SECRET_KEY : secret key for certian s3 bucket access (if not set, use IAM permission only)"
    echo "-r REGION : region for the profile set for certain s3 bucket access (if not set, use IAM permission only)"
    echo "-g : use singularity"
    echo "-V TIBANNA_VERSION : tibanna version (used in the run_task lambda that launched this instance)"
    exit "$1"
}
while getopts "i:R:I:j:l:S:L:a:s:r:gV:" opt; do
    case $opt in
        i) export JOBID=$OPTARG;;
        R) export INSTANCE_REGION=$OPTARG;;  # region of the current EC2 instance
        I) export INSTANCE_ID=$OPTARG;;  # ID of the current EC2 instance
        j) export JSON_BUCKET_NAME=$OPTARG;;  # bucket for sending run.json file. This script gets run.json file from this bucket. e.g.: 4dn-aws-pipeline-run-json
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        S) export STATUS=$OPTARG;;  # inherited STATUS env
        L) export LANGUAGE=$OPTARG;;  # workflow language
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
export LOCAL_WF_TMPDIR=$EBS_DIR/tmp
export MD5FILE=$JOBID.md5sum.txt
export INPUT_YML_FILE=inputs.yml
export DOWNLOAD_COMMAND_FILE=download_command_list.txt
export MOUNT_COMMAND_FILE=mount_command_list.txt
export ENV_FILE=env_command_list.txt
export LOGFILE=$LOCAL_OUTDIR/$JOBID.log
export LOGJSONFILE=$LOCAL_OUTDIR/$JOBID.log.json
export ERRFILE=$LOCAL_OUTDIR/$JOBID.error  # if this is found on s3, that means something went wrong.
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity| grep Account | sed 's/[^0-9]//g')


# function that executes a command and collecting log
exl(){ $@ >> $LOGFILE 2>> $LOGFILE; ERRCODE=$?; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 -a ! -z "$LOGBUCKET" ]; then send_error; fi; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong and if LOGBUCKET has already been defined, send error to s3.
exlj(){ $@ >> $LOGJSONFILE 2>> $LOGFILE; ERRCODE=$?; cat $LOGJSONFILE >> $LOGFILE; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 -a ! -z "$LOGBUCKET" ]; then send_error; fi; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong and if LOGBUCKET has already been defined, send error to s3. This one separates stdout to json as well.
exle(){ $@ >> /dev/null 2>> $LOGFILE; ERRCODE=$?; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 -a ! -z "$LOGBUCKET" ]; then send_error; fi; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong and if LOGBUCKET has already been defined, send error to s3. This one eats stdout. Useful for downloading/uploading files to/from s3, because it writes progress to stdout.
exlo(){ $@ 2>> /dev/null >> $LOGFILE; ERRCODE=$?; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 -a ! -z "$LOGBUCKET" ]; then send_error; fi; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong and if LOGBUCKET has already been defined, send error to s3. This one eats stdout. Useful for downloading/uploading files to/from s3, because it writes progress to stdout.


# function that sends log to s3 (it requires LOGBUCKET to be defined, which is done by sourcing $ENV_FILE.)
send_log(){  aws s3 cp $LOGFILE s3://$LOGBUCKET; }  ## usage: send_log (no argument)

# function that sends error file to s3 to notify something went wrong.
send_error(){  touch $ERRFILE; aws s3 cp $ERRFILE s3://$LOGBUCKET; }  ## usage: send_log (no argument)


# EBS_DIR cannot be directly mounted to docker container since it's already a mount point for EBS,
# so mount /mnt/data1/ instead and create a symlink.
ln -s /mnt/$EBS_DIR $EBS_DIR


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


# log the first message from the container
exl echo
exl echo "## AWSF Docker container created"


# create subdirectories
exl mkdir -p $LOCAL_INPUT_DIR
exl mkdir -p $LOCAL_WFDIR


# set additional profile
echo -ne "$ACCESS_KEY\n$SECRET_KEY\n$REGION\njson" | aws configure --profile user1


# getting run.json file
exl echo
exl echo "## Downloading and parsing run.json file"
exl cd /home/ubuntu/
exl aws s3 cp s3://$JSON_BUCKET_NAME/$RUN_JSON_FILE_NAME .
exl chmod -R +x .
exl awsf3 decode_run_json -i $RUN_JSON_FILE_NAME


# setting additional env variables
exl source $ENV_FILE
send_log


### download cwl from github or any other url.
exl echo
exl echo "## Downloading workflow files"
exl awsf3 download_workflow


# set up cronjojb for top command
cwd0=$(pwd)
cd ~
echo "*/1 * * * * top -b | head -15 >> $LOGFILE; du -h $LOCAL_INPUT_DIR/ >> $LOGFILE; du -h $LOCAL_WF_TMPDIR*/ >> $LOGFILE; du -h $LOCAL_OUTDIR/ >> $LOGFILE; aws s3 cp $LOGFILE s3://$LOGBUCKET &>/dev/null" >> cloudwatch.jobs
echo "*/1 * * * * send_log" >> cloudwatch.jobs
cat cloudwatch.jobs | crontab -
cd $cwd0


# docker start
service docker start


### log into ECR if necessary
exl echo
exl echo "## Logging into ECR"
if [[ ! -z "$TIBANNA_VERSION" && "$TIBANNA_VERSION" > '0.18' ]]; then
  exlo docker login --username AWS --password $(aws ecr get-login-password --region $INSTANCE_REGION) $AWS_ACCOUNT_ID.dkr.ecr.$INSTANCE_REGION.amazonaws.com;
fi
send_log

### download data & reference files from s3
exl echo
exl echo "## Downloading data & reference files from S3"
exl date 
exl cat $DOWNLOAD_COMMAND_FILE
exle source $DOWNLOAD_COMMAND_FILE 
exl date
send_log 

### mount input buckets
exl echo
exl echo "## Mounting input S3 buckets"
exl date
exl cat $MOUNT_COMMAND_FILE
exle source $MOUNT_COMMAND_FILE
exl date
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

### run command
exl echo
exl echo "## Running CWL/WDL/Snakemake/Shell commands"
exl echo "current directory="$(pwd)
cwd0=$(pwd)
cd $LOCAL_WFDIR  
mkdir -p $LOCAL_WF_TMPDIR
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
    pip uninstall -y cwltool
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
exl echo
exl echo "## Calculating md5sum of output files"
exl date
md5sum $LOCAL_OUTDIR/* | grep -v "$LOGFILE" >> $MD5FILE ;  ## calculate md5sum for output files (except log file, to avoid confusion)
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
  cd $LOCAL_WFDIR
  find . -type f -name 'stdout' -or -name 'stderr' -or -name 'script' -or \
-name '*.qc' -or -name '*.txt' -or -name '*.log' -or -name '*.png' -or -name '*.pdf' \
| xargs tar -zcvf debug.tar.gz
  exle aws s3 cp debug.tar.gz s3://$LOGBUCKET/$JOBID.debug.tar.gz
fi

exl echo
exl echo "## Uploading output files to S3"
if [[ $LANGUAGE == 'wdl' ]]
then
  LANGUAGE_OPTION='-L wdl'
elif [[ $LANGUAGE == 'snakemake' ]]
then
  LANGUAGE_OPTION='-L snakemake'
elif [[ $LANGUAGE == 'shell' ]]
then
  LANGUAGE_OPTION='-L shell'
else
  LANGUAGE_OPTION=
fi
exl awsf3 upload_output_update_json -i $RUN_JSON_FILE_NAME -e $LOGJSONFILE -l $LOGFILE -m $LOCAL_OUTDIR/$MD5FILE -o $POSTRUN_JSON_FILE_NAME $LANGUAGE_OPTION
mv $POSTRUN_JSON_FILE_NAME $RUN_JSON_FILE_NAME
send_log
 
### updating status
exl echo
exl echo "## Updating postrun json file with status, time stamp, input & output size"
# status report should be improved.
if [ $(echo $STATUS| sed 's/0//g' | sed 's/,//g') ]; then export JOB_STATUS=$STATUS ; else export JOB_STATUS=0; fi ## if STATUS is 21,0,0,1 JOB_STATUS is 21,0,0,1. If STATUS is 0,0,0,0,0,0, JOB_STATUS is 0.
# This env variable (JOB_STATUS) will be read by aws_update_run_json.py and the result will go into $POSTRUN_JSON_FILE_NAME. 

### create a postrun.json file that contains the information in the run.json file and additional information (status, stop_time)
export INPUTSIZE=$(du -csh /data1/input| tail -1 | cut -f1)
export TEMPSIZE=$(du -csh /data1/tmp*| tail -1 | cut -f1)
export OUTPUTSIZE=$(du -csh /data1/out| tail -1 | cut -f1)

# update postrun json
exl awsf3 update_postrun_json -i $RUN_JSON_FILE_NAME -o $POSTRUN_JSON_FILE_NAME

# send postrun json to s3
exl echo
exl echo "## Uploading postrun json file"
if [[ $PUBLIC_POSTRUN_JSON == '1' ]]
then
  exle aws s3 cp $POSTRUN_JSON_FILE_NAME s3://$LOGBUCKET/$POSTRUN_JSON_FILE_NAME --acl public-read
else
  exle aws s3 cp $POSTRUN_JSON_FILE_NAME s3://$LOGBUCKET/$POSTRUN_JSON_FILE_NAME
fi

# send the final log
exl echo
exl echo "Done"
exl date
send_log

# send success message
if [ ! -z $JOB_STATUS -a $JOB_STATUS == 0 ]; then touch $JOBID.success; aws s3 cp $JOBID.success s3://$LOGBUCKET/; fi
