#!/bin/bash
JOBID=$1
SHUTDOWN_MIN=60   #Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging.
EBS_DEVICE=/dev/xvdb
JSON_BUCKET_NAME=4dn-aws-pipeline-run-json
RUN_JSON_FILE_NAME=$JOBID.run.json
POSTRUN_JSON_FILE_NAME=$JOBID.postrun.json
EBS_DIR=/data1  ## WARNING: also hardcoded in aws_decode_run_json.py
LOCAL_OUTDIR=$EBS_DIR/out  
LOGFILE=$LOCAL_OUTDIR/log
LOCAL_CWLDIR=$LOCAL_OUTDIR ## cwl-runner directory handling is so great that we had to do this..
LOCAL_INPUT_DIR=$EBS_DIR/input  ## WARNING: also hardcoded in aws_decode_run_json.py
LOCAL_REFERENCE_DIR=$EBS_DIR/reference  ## WARNING: also hardcoded in aws_decode_run_json.py
MD5FILE=md5sum.txt
SCRIPTS_URL=https://raw.githubusercontent.com/hms-dbmi/tibanna/master/
INPUT_YML_FILE=inputs.yml
DOWNLOAD_COMMAND_FILE=download_command_list.txt
ENV_FILE=env_command_list.txt
STATUS=0

### start with a log under the home directory for ec2-user. Later this will be moved to the output directory, once the ebs is mounted.
cd /home/ec2-user/
date > templog___ ; STATUS+=,$?  ## start time
 
### 2. get the run.json file and parse it to get environmental variables CWL_URL, MAIN_CWL, CWL_FILES and OUTBUCKET and create an inputs.yml file (INPUT_YML_FILE).
wget $SCRIPTS_URL/aws_decode_run_json.py >> templog___ 2>> templog___ ; STATUS+=,$?
wget $SCRIPTS_URL/aws_update_run_json.py >> templog___ 2>> templog___ ; STATUS+=,$?

aws s3 cp s3://$JSON_BUCKET_NAME/$RUN_JSON_FILE_NAME . >> templog___ 2>> templog___ ; STATUS+=,$?
chmod +x ./*py >> templog___ 2>> templog___ ; STATUS+=,$?
./aws_decode_run_json.py $RUN_JSON_FILE_NAME >> templog___ 2>> templog___ ;  STATUS+=,$?
source $ENV_FILE >> templog___ 2>> templog___ ;  STATUS+=,$?

# function that sends log to s3 (it requires OUTBUCKET to be defined, which is done by sourcing $ENV_FILE.)
send_log(){
   aws s3 cp $LOGFILE s3://$OUTBUCKET/$LOGFILE
}

###  mount the EBS volume to the EBS_DIR
lsblk >> templog___ 2>> templog___; STATUS+=,$?
mkfs -t ext4 $EBS_DEVICE >> templog___ 2>> templog___; STATUS+=,$?  # creating a file system
mkdir $EBS_DIR >> templog___ 2>> templog___; STATUS+=,$?  
mount $EBS_DEVICE $EBS_DIR >> templog___ 2>> templog___; STATUS+=,$?  # mount
chmod 777 $EBS_DIR >> templog___ 2>> templog___; STATUS+=,$?

### restart docker so the mounting can take effect
service docker restart

### create subdirectories under the mounted ebs directory and move log file into that output directory
mkdir -p $LOCAL_OUTDIR; STATUS+=,$?
mkdir -p $LOCAL_INPUT_DIR; STATUS+=,$?
mkdir -p $LOCAL_REFERENCE_DIR; STATUS+=,$?
mkdir -p $LOCAL_CWLDIR; STATUS+=,$?
mv templog___ $LOGFILE
send_log

# download cwl from github or any other url.
for CWL_FILE in $MAIN_CWL $CWL_FILES
do
 wget -O$LOCAL_CWLDIR/$CWL_FILE $CWL_URL/$CWL_FILE >> $LOGFILE 2>> $LOGFILE; STATUS+=,$?
done
# download data & reference files from s3
cat $DOWNLOAD_COMMAND_FILE >> $LOGFILE 2>> $LOGFILE ; STATUS+=,$?
source $DOWNLOAD_COMMAND_FILE >> $LOGFILE 2>> $LOGFILE   ; STATUS+=,$?
ls >> $LOGFILE  ; STATUS+=,$?
send_log 

df >> $LOGFILE ; STATUS+=,$?
pwd >> $LOGFILE ; STATUS+=,$?
ls -lh / >> $LOGFILE; STATUS+=,$?
ls -lhR $EBS_DIR >> $LOGFILE; STATUS+=,$?
send_log

### 3. activate cwl-runner environment
source /home/ec2-user/venv/cwl/bin/activate  ; STATUS+=,$?
### 5. run command
cwd0=$(pwd)
cd $LOCAL_OUTDIR  ## so that other downstream cwl files can be accessed and so that the output files can be captured.
cwl-runner $LOCAL_CWLDIR/$CWL_FILE $cwd0/$INPUT_YML_FILE >> $LOGFILE 2>> $LOGFILE   ; STATUS+=,$?
deactivate  ; STATUS+=,$?
cd $cwd0
send_log 

### delete cwl files so that they won't get to s3
for CWL_FILE in $MAIN_CWL $CWL_FILES
do
 rm -f $LOCAL_CWLDIR/$CWL_FILE >> $LOGFILE 2>> $LOGFILE; STATUS+=,$?
done

### 6. copy output files to s3
md5sum $LOCAL_OUTDIR/* | grep -v "$LOGFILE" >> $MD5FILE ; STATUS+=,$?  ## calculate md5sum for output files (except log file, to avoid confusion)
mv $MD5FILE $LOCAL_OUTDIR  ; STATUS+=,$?
date >> $LOGFILE  ;   STATUS+=,$? ## done time
send_log
aws s3 cp --recursive $LOCAL_OUTDIR s3://$OUTBUCKET >> $LOGFILE 2>> $LOGFILE ; STATUS+=,$?
send_log
#<calculate md5sum for uploaded output files> ## is there a direct way to get this for a file on s3?
 
### 7. updating status
# status report should be improved.
if [ `echo $STATUS| sed 's/0//g' | sed 's/,//g'` ]; then export JOB_STATUS=$STATUS ; else export JOB_STATUS=0; fi ## if STATUS is 21,0,0,1 JOB_STATUS is 21,0,0,1. If STATUS is 0,0,0,0,0,0, JOB_STATUS is 0.
# This env variable (JOB_STATUS) will be read by aws_update_run_json.py and the result will go into $POSTRUN_JSON_FILE_NAME. 
### 8. create a postrun.json file that contains the information in the run.json file and additional information (status, stop_time)
./aws_update_run_json.py $RUN_JSON_FILE_NAME $POSTRUN_JSON_FILE_NAME
aws s3 cp $POSTRUN_JSON_FILE_NAME s3://$OUTBUCKET/$POSTRUN_JSON_FILE_NAME
 
### 8. how do we send a signal that the job finished?
#<some script>
 
### 9. self-terminate
# (option 1)  ## This is the easiest if the 'shutdown behavior' set to 'terminate' for the instance at launch.
sudo shutdown -h $SHUTDOWN_MIN 
# (option 2)  ## This works only if the instance is given a proper permission (This is more standard but I never actually got it to work)
#id=$(ec2-metadata -i|cut -d' ' -f2)
#aws ec2 terminate-instances --instance-ids $id
 

