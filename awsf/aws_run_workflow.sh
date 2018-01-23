#!/bin/bash
export JOBID=$1
export SHUTDOWN_MIN=$2   # Possibly user can specify SHUTDOWN_MIN to hold it for a while for debugging.
export JSON_BUCKET_NAME=$3  # bucket for sending run.json file. This script gets run.json file from this bucket. e.g.: 4dn-aws-pipeline-run-json
export LOGBUCKET=$4  # bucket for sending log file
export SCRIPTS_URL=$5  # Tibanna repo url (e.g. https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/)
export PASSWORD=$6  # Password for ssh connection for user ec2-user
export EBS_DEVICE=/dev/xvdb
export RUN_JSON_FILE_NAME=$JOBID.run.json
export POSTRUN_JSON_FILE_NAME=$JOBID.postrun.json
export EBS_DIR=/data1  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_OUTDIR=$EBS_DIR/out  
export LOCAL_CWLDIR=$EBS_DIR/cwl 
export LOCAL_INPUT_DIR=$EBS_DIR/input  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_REFERENCE_DIR=$EBS_DIR/reference  ## WARNING: also hardcoded in aws_decode_run_json.py
export LOCAL_CWL_TMPDIR=$EBS_DIR/tmp
export MD5FILE=$JOBID.md5sum.txt
export INPUT_YML_FILE=inputs.yml
export DOWNLOAD_COMMAND_FILE=download_command_list.txt
export ENV_FILE=env_command_list.txt
export LOGFILE1=templog___  # log before mounting ebs
export LOGFILE2=$LOCAL_OUTDIR/$JOBID.log
export LOGJSONFILE=$LOCAL_OUTDIR/$JOBID.log.json
export STATUS=0
export ERRFILE=$LOCAL_OUTDIR/$JOBID.error  # if this is found on s3, that means something went wrong.
export INSTANCE_ID=$(ec2-metadata -i|cut -d' ' -f2)

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
    du -h /data1/input/ >> $LOGFILE; \
    du -h /data1/tmp* >> $LOGFILE; \
    du -h /ata1/out >> $LOGFILE; \
    aws s3 cp $LOGFILE s3://$LOGBUCKET" &>/dev/null; 
}  ## usage: send_log_regularly (no argument)

# function that sends error file to s3 to notify something went wrong.
send_error(){  touch $ERRFILE; aws s3 cp $ERRFILE s3://$LOGBUCKET; }  ## usage: send_log (no argument)


### start with a log under the home directory for ec2-user. Later this will be moved to the output directory, once the ebs is mounted.
LOGFILE=$LOGFILE1
cd /home/ec2-user/
touch $LOGFILE 
exl date  ## start logging

### sshd configure for password recognition
-echo -ne "$PASSWORD\n$PASSWORD\n" | passwd ec2-user
-sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config
-exl service sshd restart

### sshd configure for password recognition
if [ ! -z $PASSWORD ]; then
  echo -ne "$PASSWORD\n$PASSWORD\n" | sudo passwd ec2-user
  cat /etc/ssh/sshd_config | sed 's/PasswordAuthentication no/PasswordAuthentication yes/g' | sed 's/#PasswordAuthentication no/PasswordAuthentication yes/g' > tmpp
  mv tmpp /etc/ssh/sshd_config
  exl service sshd restart
fi


### 2. get the run.json file and parse it to get environmental variables CWL_URL, MAIN_CWL, CWL_FILES and LOGBUCKET and create an inputs.yml file (INPUT_YML_FILE).
exl wget $SCRIPTS_URL/aws_decode_run_json.py
exl wget $SCRIPTS_URL/aws_update_run_json.py
exl wget $SCRIPTS_URL/aws_upload_output_update_json.py

exl echo $JSON_BUCKET_NAME
exl aws s3 cp s3://$JSON_BUCKET_NAME/$RUN_JSON_FILE_NAME .
exl chown -R ec2-user .
exl chmod -R +x .
exl ./aws_decode_run_json.py $RUN_JSON_FILE_NAME
exl source $ENV_FILE


###  mount the EBS volume to the EBS_DIR
exl lsblk $TMPLOGFILE
exl mkfs -t ext4 $EBS_DEVICE # creating a file system
exl mkdir $EBS_DIR
exl mount $EBS_DEVICE $EBS_DIR # mount
exl chown -R ec2-user $EBS_DIR
exl chmod -R +x $EBS_DIR

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
#exl source /home/ec2-user/venv/toil/bin/activate  # use toil instaed

### run command
cwd0=$(pwd)
cd $LOCAL_CWLDIR  
mkdir -p $LOCAL_CWL_TMPDIR
#pip install cwlref-runner --upgrade  ## temporary solution to enable --no-match-user option
#yum install -y git gcc
#git clone https://github.com/SooLee/cwltool
#cd cwltool
#pip install .
#cd ..
send_log_regularly &
#exl cwltool --no-read-only --no-match-user --outdir $LOCAL_OUTDIR --tmp-outdir-prefix $LOCAL_CWL_TMPDIR --tmpdir-prefix $LOCAL_CWL_TMPDIR $LOCAL_CWLDIR/$MAIN_CWL $cwd0/$INPUT_YML_FILE
alias cwl-runner=cwltool
#exlj cwl-runner --copy-outputs --no-read-only --no-match-user --outdir $LOCAL_OUTDIR --tmp-outdir-prefix $LOCAL_CWL_TMPDIR --tmpdir-prefix $LOCAL_CWL_TMPDIR $MAIN_CWL $cwd0/$INPUT_YML_FILE
exlj cwltool --non-strict --copy-outputs --no-read-only --no-match-user --outdir $LOCAL_OUTDIR --tmp-outdir-prefix $LOCAL_CWL_TMPDIR --tmpdir-prefix $LOCAL_CWL_TMPDIR $MAIN_CWL $cwd0/$INPUT_YML_FILE
#exl cwl-runner $LOCAL_CWLDIR/$MAIN_CWL $cwd0/$INPUT_YML_FILE
deactivate
cd $cwd0
send_log 

### copy output files to s3
md5sum $LOCAL_OUTDIR/* | grep -v "$LOGFILE" >> $MD5FILE ;  ## calculate md5sum for output files (except log file, to avoid confusion)
mv $MD5FILE $LOCAL_OUTDIR
exl date ## done time
send_log
exl ls -lhtr $LOCAL_OUTDIR/
#exle aws s3 cp --recursive $LOCAL_OUTDIR s3://$OUTBUCKET
pip install boto3
exle ./aws_upload_output_update_json.py $RUN_JSON_FILE_NAME $LOGJSONFILE $POSTRUN_JSON_FILE_NAME
mv $POSTRUN_JSON_FILE_NAME $RUN_JSON_FILE_NAME
send_log
 
### updating status
# status report should be improved.
if [ `echo $STATUS| sed 's/0//g' | sed 's/,//g'` ]; then export JOB_STATUS=$STATUS ; else export JOB_STATUS=0; fi ## if STATUS is 21,0,0,1 JOB_STATUS is 21,0,0,1. If STATUS is 0,0,0,0,0,0, JOB_STATUS is 0.
# This env variable (JOB_STATUS) will be read by aws_update_run_json.py and the result will go into $POSTRUN_JSON_FILE_NAME. 
### 8. create a postrun.json file that contains the information in the run.json file and additional information (status, stop_time)
export INPUTSIZE=$(du -csh /data1/input| tail -1 | cut -f1)
export TEMPSIZE=$(du -csh /data1/tmp*| tail -1 | | cut -f1)
export OUTPUTSIZE=$(du -csh /data1/out| tail -1 | cut -f1)

exl ./aws_update_run_json.py $RUN_JSON_FILE_NAME $POSTRUN_JSON_FILE_NAME
exle aws s3 cp $POSTRUN_JSON_FILE_NAME s3://$LOGBUCKET/$POSTRUN_JSON_FILE_NAME
if [ ! -z $JOB_STATUS -a $JOB_STATUS == 0 ]; then touch $JOBID.success; aws s3 cp $JOBID.success s3://$LOGBUCKET/; fi
send_log

### how do we send a signal that the job finished?
#<some script>
 
### self-terminate
# (option 1)  ## This is the easiest if the 'shutdown behavior' set to 'terminate' for the instance at launch.
sudo shutdown -h $SHUTDOWN_MIN 
# (option 2)  ## This works only if the instance is given a proper permission (This is more standard but I never actually got it to work)
#id=$(ec2-metadata -i|cut -d' ' -f2)
#aws ec2 terminate-instances --instance-ids $id
 

