#!/bin/bash
shopt -s extglob

printHelpAndExit() {
    echo "Usage: ${0##*/} -l LOGBUCKET -S STATUS -L LOGFILE -E ERRFILE"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-S STATUS: inherited status environment variable (required)"
    echo "-L LOGFILE : path of log file (required)"
    echo "-E ERRFILE : path of error file (required)"
    exit "$1"
}
while getopts "l:S:L:E:" opt; do
    case $opt in
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        S) export STATUS=$OPTARG;;  # inherited STATUS env
        L) export LOGFILE=$OPTARG;;  # path of log file
        E) export ERRFILE=$OPTARG;;  # path of error file
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done


echo "LOGFILE=$LOGFILE"

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

# head of a command - for avoiding a pipe
head_command() { $@ | head -15; }

exl echo
exl head_command top -b -n 1
send_log
