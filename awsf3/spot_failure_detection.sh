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
        j) export JOBID=$OPTARG;;  # job id
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

sleep $SLEEP

### send spot_failure message to S3
if [ ! -f $JOBID.spot_failure ]; then
    # https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html
    # We are using IMDSv1 for performance reasons and simplicity.
    status_code=`curl -s -o /dev/null -I -w "%{http_code}" http://169.254.169.254/latest/meta-data/spot/instance-action`
    # This spot/instance-action is present only if the Spot Instance has been marked for hibernate, stop, or terminate.
    # Therefore it is sufficient to check if the request was successul.
    if [ "$status_code" = "200" ]; then
        touch $JOBID.spot_failure
        aws s3 cp $JOBID.spot_failure s3://$LOGBUCKET/$JOBID.spot_failure   
    fi 
fi


