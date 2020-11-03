#!/bin/bash
shopt -s extglob

printHelpAndExit() {
    echo "Usage: ${0##*/} -l LOGBUCKET -T TOPFILE"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-T TOPFILE : path of log file (required)"
    exit "$1"
}
while getopts "l:T:" opt; do
    case $opt in
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        T) export TOPFILE=$OPTARG;;  # path of log file
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

# function that executes a command and collecting log
exl(){ $@ >> $TOPFILE 2>> $TOPFILE; } ## usage: exl command

# function that sends log to s3
send_log(){  aws s3 cp $TOPFILE s3://$LOGBUCKET &>/dev/null; }  ## usage: send_log (no argument)

# head of a command - for avoiding a pipe
head_command() { $@ | head -15; }

exl echo
exl head_command top -b -n 1
exl echo
send_log
