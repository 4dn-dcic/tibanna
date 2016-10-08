#!/bin/bash
JOBID=$1
SHUTDOWN_MIN=now   #Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging.
EBS_DEVICE=/dev/xvdb
JSON_BUCKET_NAME=4dn-aws-pipeline-run-json
RUN_JSON_FILE_NAME=$JOBID.run.json
POSTRUN_JSON_FILE_NAME=$JOBID.postrun.json
EBS_DIR=/data1  ## WARNING: also hardcoded in aws_decode_run_json.py
LOCAL_OUTDIR=$EBS_DIR/out  
LOCAL_CWLDIR=$LOCAL_OUTDIR ## cwl-runner directory handling is so great that we had to do this..
LOCAL_INPUT_DIR=$EBS_DIR/input  ## WARNING: also hardcoded in aws_decode_run_json.py
LOCAL_REFERENCE_DIR=$EBS_DIR/reference  ## WARNING: also hardcoded in aws_decode_run_json.py
MD5FILE=$JOBID.md5sum.txt
SCRIPTS_URL=https://raw.githubusercontent.com/hms-dbmi/tibanna/master/
INPUT_YML_FILE=inputs.yml
DOWNLOAD_COMMAND_FILE=download_command_list.txt
ENV_FILE=env_command_list.txt
LOGFILE1=templog___  # log before mounting ebs
LOGFILE2=$LOCAL_OUTDIR/$JOBID.log
STATUS=0
ERRFILE=$LOCAL_OUTDIR/$JOBID.error  # if this is found on s3, that means something went wrong.

# function that executes a command and collecting log
exl(){ $@ >> $LOGFILE 2>> $LOGFILE; ERRCODE=$?; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 -a ! -z "$OUTBUCKET" ]; then send_error; fi; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong and if OUTBUCKET has already been defined, send error to s3.
exle(){ $@ >> /dev/null 2>> $LOGFILE; ERRCODE=$?; STATUS+=,$ERRCODE; if [ "$ERRCODE" -ne 0 -a ! -z "$OUTBUCKET" ]; then send_error; fi; } ## usage: exl command  ## ERRCODE has the error code for the command. if something is wrong and if OUTBUCKET has already been defined, send error to s3. This one eats stdout. Useful for downloading/uploading files to/from s3, because it writes progress to stdout.

# function that sends log to s3 (it requires OUTBUCKET to be defined, which is done by sourcing $ENV_FILE.)
send_log(){  aws s3 cp $LOGFILE s3://$OUTBUCKET; }  ## usage: send_log (no argument)

# function that sends error file to s3 to notify something went wrong.
send_error(){  touch $ERRFILE; aws s3 cp $ERRFILE s3://$OUTBUCKET; }  ## usage: send_log (no argument)


### start with a log under the home directory for ec2-user. Later this will be moved to the output directory, once the ebs is mounted.
LOGFILE=$LOGFILE1
cd /home/ec2-user/
touch $LOGFILE 
exl date  ## start logging
 
### 2. get the run.json file and parse it to get environmental variables CWL_URL, MAIN_CWL, CWL_FILES and OUTBUCKET and create an inputs.yml file (INPUT_YML_FILE).
exl wget $SCRIPTS_URL/aws_decode_run_json.py
exl wget $SCRIPTS_URL/aws_update_run_json.py

exl aws s3 cp s3://$JSON_BUCKET_NAME/$RUN_JSON_FILE_NAME .
exl chmod +x ./*py
exl ./aws_decode_run_json.py $RUN_JSON_FILE_NAME
exl source $ENV_FILE

# first create an output bucket/directory
touch $JOBID.job_started
aws s3 cp $JOBID.job_started s3://$OUTBUCKET/$JOBID.job_started


###  mount the EBS volume to the EBS_DIR
exl lsblk $TMPLOGFILE
exl mkfs -t ext4 $EBS_DEVICE # creating a file system
exl mkdir $EBS_DIR
exl mount $EBS_DEVICE $EBS_DIR # mount
exl chmod 777 $EBS_DIR

### restart docker so the mounting can take effect
exl service docker restart

### create subdirectories under the mounted ebs directory and move log file into that output directory
exl mkdir -p $LOCAL_OUTDIR
exl mkdir -p $LOCAL_INPUT_DIR
exl mkdir -p $LOCAL_REFERENCE_DIR
exl mkdir -p $LOCAL_CWLDIR
mv $LOGFILE1 $LOGFILE2
LOGFILE=$LOGFILE2
send_log


### download cwl from github or any other url.
for CWL_FILE in $MAIN_CWL $CWL_FILES
do
 exl wget -O$LOCAL_CWLDIR/$CWL_FILE $CWL_URL/$CWL_FILE
done

### download data & reference files from s3
exl cat $DOWNLOAD_COMMAND_FILE
exl date 
exle source $DOWNLOAD_COMMAND_FILE 
exl date
exl ls
send_log 

### just some more logging
exl df
exl pwd
exl ls -lh /
exl ls -lhR $EBS_DIR
send_log

### activate cwl-runner environment
exl source /home/ec2-user/venv/cwl/bin/activate

### run command
cwd0=$(pwd)
cd $LOCAL_OUTDIR  ## so that other downstream cwl files can be accessed and so that the output files can be captured.
exl cwl-runner $LOCAL_CWLDIR/$MAIN_CWL $cwd0/$INPUT_YML_FILE
deactivate
cd $cwd0
send_log 

### delete cwl files so that they won't get to s3
for CWL_FILE in $MAIN_CWL $CWL_FILES
do
 exl rm -f $LOCAL_CWLDIR/$CWL_FILE
done

### copy output files to s3
md5sum $LOCAL_OUTDIR/* | grep -v "$LOGFILE" >> $MD5FILE ;  ## calculate md5sum for output files (except log file, to avoid confusion)
mv $MD5FILE $LOCAL_OUTDIR
exl date ## done time
send_log
exl ls -lhtr $LOCAL_OUTDIR/
exle aws s3 cp --recursive $LOCAL_OUTDIR s3://$OUTBUCKET
send_log
 
### updating status
# status report should be improved.
if [ `echo $STATUS| sed 's/0//g' | sed 's/,//g'` ]; then export JOB_STATUS=$STATUS ; else export JOB_STATUS=0; fi ## if STATUS is 21,0,0,1 JOB_STATUS is 21,0,0,1. If STATUS is 0,0,0,0,0,0, JOB_STATUS is 0.
# This env variable (JOB_STATUS) will be read by aws_update_run_json.py and the result will go into $POSTRUN_JSON_FILE_NAME. 
### 8. create a postrun.json file that contains the information in the run.json file and additional information (status, stop_time)
exl ./aws_update_run_json.py $RUN_JSON_FILE_NAME $POSTRUN_JSON_FILE_NAME
exle aws s3 cp $POSTRUN_JSON_FILE_NAME s3://$OUTBUCKET/$POSTRUN_JSON_FILE_NAME
if [ ! -z $JOB_STATUS -a $JOB_STATUS == 0 ]; then touch $JOBID.success; aws s3 cp $JOBID.success s3://$OUTBUCKET/; fi
send_log

### how do we send a signal that the job finished?
#<some script>
 
### self-terminate
# (option 1)  ## This is the easiest if the 'shutdown behavior' set to 'terminate' for the instance at launch.
sudo shutdown -h $SHUTDOWN_MIN 
# (option 2)  ## This works only if the instance is given a proper permission (This is more standard but I never actually got it to work)
#id=$(ec2-metadata -i|cut -d' ' -f2)
#aws ec2 terminate-instances --instance-ids $id
 

