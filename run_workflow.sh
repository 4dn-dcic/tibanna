#!/bin/bash
JOBID=v989328isyrbag02   ### This part can be changed by the lambda
RUN_SCRIPT=aws_run_workflow.sh
SCRIPT_BUCKET=4dn-aws-pipeline-mng-scripts
aws s3 cp s3://$SCRIPT_BUCKET/$RUN_SCRIPT .
chmod +x $RUN_SCRIPT
source $RUN_SCRIPT $JOBID
