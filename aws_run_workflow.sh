#!/bin/bash
JOBID=$1
SHUTDOWN_MIN=60   #Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging.
EBS_DEVICE=/dev/xvdb
JSON_BUCKET_NAME=4dn-aws-pipeline-run-json
RUN_JSON_FILE_NAME=$JOBID.run.json
POSTRUN_JSON_FILE_NAME=$JOBID.postrun.json
EBS_DIR=/data1
LOCAL_OUTDIR=$(pwd)/out
LOGFILE=$LOCAL_OUTDIR/log
LOCAL_CWLDIR=$EBS_DIR/cwl
MD5FILE=md5sum.txt
SCRIPTS_URL=https://raw.githubusercontent.com/hms-dbmi/tibanna/master/
INPUT_YML_FILE=inputs.yml
DOWNLOAD_COMMAND_FILE=download_command_list.txt
ENV_FILE=env_command_list.txt
STATUS=0



### 1. create an output and log directory
mkdir -p $LOCAL_OUTDIR; STATUS+=,$?
date > $LOGFILE; STATUS+=,$?  ## start time

 
### 2. get the run.json file and parse it to get environmental variables CWL_URL, MAIN_CWL, CWL_FILES and OUTBUCKET and create an inputs.yml file (INPUT_YML_FILE).
wget $SCRIPTS_URL/aws_decode_run_json.py ; STATUS+=,$?
wget $SCRIPTS_URL/aws_update_run_json.py ; STATUS+=,$?

aws s3 cp s3://$JSON_BUCKET_NAME/$RUN_JSON_FILE_NAME . ; STATUS+=,$?
chmod +x ./*py  ; STATUS+=,$?
./aws_decode_run_json.py $RUN_JSON_FILE_NAME  ;  STATUS+=,$?
source $ENV_FILE ;  STATUS+=,$?

# function that sends log to s3 (it requires OUTBUCKET to be defined, which is done by sourcing $ENV_FILE.)
send_log(){
   aws s3 cp $LOGFILE s3://$OUTBUCKET/$LOGFILE
}
send_log 

###  mount the EBS volume to the EBS_DIR
mkfs -t ext4 $EBS_DEVICE >> $LOGFILE 2>> $LOGFILE; STATUS+=,$?  # creating a file system
mkdir $EBS_DIR >> $LOGFILE 2>> $LOGFILE; STATUS+=,$?  
mount /dev/xvdb $EBS_DIR >> $LOGFILE 2>> $LOGFILE; STATUS+=,$?  # mount
sudo chmod 777 $EBS_DIR >> $LOGFILE 2>> $LOGFILE; STATUS+=,$?
cd $EBS_DIR;  STATUS+=,$?
send_log

# download cwl from github or any other url.
for CWL_FILE in $MAIN_CWL $CWL_FILES
do
 wget -O$LOCAL_CWLDIR/$CWL_FILE $CWL_URL/$CWL_FILE >> $LOGFILE 2>> $LOGFILE; STATUS+=,$?
done
# download data & reference files from s3
source $DOWNLOAD_COMMAND_FILE >> $LOGFILE 2>> $LOGFILE   ; STATUS+=,$?
ls >> $LOGFILE  ; STATUS+=,$?
send_log 

df >> $LOGFILE ; STATUS+=,$?
pwd >> $LOGFILE ; STATUS+=,$?
ls -lh / >> $LOGFILE; STATUS+=,$?
send_log

### 3. activate cwl-runner environment
source venv/cwl/bin/activate  ; STATUS+=,$?
### 5. run command
cwl-runner --outdir $LOCAL_OUTDIR --leave-tmpdir $LOCAL_CWLDIR/$CWL_FILE $INPUT_YML_FILE >> $LOGFILE 2>> $LOGFILE   ; STATUS+=,$?
deactivate  ; STATUS+=,$?
send_log 

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
 

