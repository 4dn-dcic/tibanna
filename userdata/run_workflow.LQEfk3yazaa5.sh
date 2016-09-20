#!/bin/bash
JOBID=LQEfk3yazaa5
RUN_SCRIPT=aws_run_workflow.sh
SCRIPT_URL=https://raw.githubusercontent.com/hms-dbmi/tibanna/master/
wget $SCRIPT_URL/$RUN_SCRIPT
chmod +x $RUN_SCRIPT
source $RUN_SCRIPT $JOBID
