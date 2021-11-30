#!/bin/bash
shopt -s extglob

printHelpAndExit() {
    echo "Usage: ${0##*/} -l LOGBUCKET -L LOGFILE -t TOPFILE -T TOPLATESTFILE"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-L LOGFILE : path of log file (required)"
    echo "-t TOPFILE : path of top file (required)"
    echo "-T TOPLATESTFILE : path of top_latest file (required)"
    echo "-k S3_ENCRYPT_KEY_ID : KMS key to encrypt s3 files with"
    exit "$1"
}
while getopts "l:L:t:T:k" opt; do
    case $opt in
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        L) export LOGFILE=$OPTARG;;  # path of log file
        t) export TOPFILE=$OPTARG;;  # path of top file
        T) export TOPLATESTFILE=$OPTARG;;  # path of top_latest file
        k) export S3_ENCRYPT_KEY_ID=$OPTARG;;  # KMS key ID to encrypt s3 files with
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

# function that executes a command and collecting log
extp(){ $@ > $TOPLATESTFILE; cat $TOPLATESTFILE >> $TOPFILE; } ## usage: extp command

# function that sends top to s3
send_top(){
  if [ -z "$S3_ENCRYPT_KEY_ID" ];
  then
    /usr/local/bin/aws s3 cp $TOPFILE s3://$LOGBUCKET;
  else
    /usr/local/bin/aws s3 cp $TOPFILE s3://$LOGBUCKET --sse aws:kms --sse-kms-key-id "$S3_ENCRYPT_KEY_ID";
  fi
}

# function that sends log to s3 (it requires LOGBUCKET to be defined, which is done by sourcing $ENV_FILE.)
## usage: send_log (no argument)
send_log(){
  if [ -z "$S3_ENCRYPT_KEY_ID" ];
  then
    /usr/local/bin/aws s3 cp $LOGFILE s3://$LOGBUCKET;
  else
    /usr/local/bin/aws s3 cp $LOGFILE s3://$LOGBUCKET --sse aws:kms --sse-kms-key-id "$S3_ENCRYPT_KEY_ID";
  fi
}

# add margin and timestamp to a command
stamp_command() { echo; echo -n 'Timestamp: '; date +%F-%H:%M:%S; $@; echo; }

extp stamp_command top -b -n 1 -i -c -w512
send_top
send_log

