#!/bin/bash
shopt -s extglob

printHelpAndExit() {
    echo "Usage: ${0##*/} -s SLEEP -l LOGBUCKET -j JOBID"
    echo "-s SLEEP : execution delay in seconds"
    echo "-l LOGBUCKET : bucket for sending log file (required)"
    echo "-j JOBID : jobs id"
    exit "$1"
}
while getopts "s:l:j:k:" opt; do
    case $opt in
        s) SLEEP=$OPTARG;;  # execution delay in seconds
        l) export LOGBUCKET=$OPTARG;;  # bucket for sending log file
        j) export JOBID=$OPTARG;;  # job id
        k) export S3_ENCRYPT_KEY_ID=$OPTARG;;  # KMS key ID to encrypt s3 files with
        h) printHelpAndExit 0;;
        [?]) printHelpAndExit 1;;
        esac
done

sleep $SLEEP

### Send spot_failure message to S3
if [ ! -f $JOBID.spot_failure ]; then
    # IMDSv2 token fetch
    TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
                  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" \
                  -s)

    # Query instance-action endpoint using IMDSv2
    status_code=$(curl -s -o /dev/null -w "%{http_code}" \
                  -H "X-aws-ec2-metadata-token: $TOKEN" \
                  http://169.254.169.254/latest/meta-data/spot/instance-action)
    # This spot/instance-action is present only if the Spot Instance has been marked for hibernate, stop, or terminate.
    # Therefore, it is sufficient to check if the request was successful.
    if [ "$status_code" = "200" ]; then
        touch $JOBID.spot_failure
        if [ -z "$S3_ENCRYPT_KEY_ID" ];
        then
            aws s3 cp $JOBID.spot_failure s3://$LOGBUCKET/$JOBID.spot_failure &>/dev/null;
        else
            aws s3 cp $JOBID.spot_failure s3://$LOGBUCKET/$JOBID.spot_failure --sse aws:kms --sse-kms-key-id "$S3_ENCRYPT_KEY_ID" &>/dev/null;
        fi
           
    fi 
fi


