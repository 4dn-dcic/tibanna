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

exl top -b -n 1 | head -15
send_log

