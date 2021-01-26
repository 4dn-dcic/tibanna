#!/bin/bash
shopt -s extglob

printHelpAndExit() {
    echo "Usage: ${0##*/} -l LOGBUCKET -L LOGFILE -t TOPFILE -T TOPLATESTFILE"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-L LOGFILE : path of log file (required)"
    echo "-t TOPFILE : path of top file (required)"
    echo "-T TOPLATESTFILE : path of top_latest file (required)"
    exit "$1"
}
while getopts "l:L:t:T:" opt; do
    case $opt in
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        L) export LOGFILE=$OPTARG;;  # path of log file
        t) export TOPFILE=$OPTARG;;  # path of top file
        T) export TOPLATESTFILE=$OPTARG;;  # path of top_latest file
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

# function that executes a command and collecting log
extp(){ $@ > $TOPLATESTFILE; cat $TOPLATESTFILE >> $TOPFILE; } ## usage: extp command

# function that sends log to s3
send_top(){  /usr/local/bin/aws s3 cp $TOPFILE s3://$LOGBUCKET; /usr/local/bin/aws s3 cp $TOPLATESTFILE s3://$LOGBUCKET; }  ## usage: send_top (no argument)
send_log(){  /usr/local/bin/aws s3 cp $LOGFILE s3://$LOGBUCKET; }  ## usage: send_log (no argument)

# add margin and timestamp to a command
stamp_command() { echo; echo -n 'Timestamp: '; date +%F-%H:%M:%S; $@; echo; }

extp stamp_command top -b -n 1 -i -c -w512
send_top
send_log

