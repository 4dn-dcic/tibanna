#!/bin/bash
shopt -s extglob

printHelpAndExit() {
    echo "Usage: ${0##*/} -s SLEEP -l LOGBUCKET -j JOBID"
    echo "-s SLEEP : execution delay in seconds"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-j JOBID : jobs id"
    exit "$1"
}
while getopts "s:l:j:" opt; do
    case $opt in
        s) SLEEP=$OPTARG;;  # execution delay in seconds
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        j) export JOBID=$OPTARG;;  # job od
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

sleep $SLEEP

### send spot_failure message to S3
if [ ! -f $JOBID.spot_failure ]; then
    instance_action=$(ec2metadata --instance-action)
    if [ "$instance_action" != "none" ]; 
        touch $JOBID.spot_failure
        echo "$instance_action" > $JOBID.spot_failure
        aws s3 cp $JOBID.spot_failure s3://$LOGBUCKET/$JOBID.spot_failure
    fi    
fi

#echo "$LOGBUCKET / $JOBID"

