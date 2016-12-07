#!/bin/bash
JOBID=v989328isyrbag02
RUN_SCRIPT=aws_run_workflow.sh
SCRIPT_URL=https://raw.githubusercontent.com/hms-dbmi/tibanna/dev/
wget $SCRIPT_URL/$RUN_SCRIPT
chmod +x $RUN_SCRIPT
source $RUN_SCRIPT $JOBID
