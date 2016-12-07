#!/bin/bash
JOBID=$1
USERDATA_DIR=$2
SHUTDOWN_MIN=$3
[!-d $USERDATA_DIR] || mkdir -p $USERDATA_DIR
RUN_WORKFLOW_FILE=$USERDATA_DIR/run_workflow.$JOBID.sh
SCRIPT_URL=https://raw.githubusercontent.com/hms-dbmi/tibanna/master/
echo "#!/bin/bash" > $RUN_WORKFLOW_FILE
echo "JOBID=$JOBID" >> $RUN_WORKFLOW_FILE
echo "RUN_SCRIPT=aws_run_workflow.sh" >> $RUN_WORKFLOW_FILE
echo "SCRIPT_URL=$SCRIPT_URL" >> $RUN_WORKFLOW_FILE
echo "wget \$SCRIPT_URL/\$RUN_SCRIPT" >> $RUN_WORKFLOW_FILE
echo "chmod +x \$RUN_SCRIPT" >> $RUN_WORKFLOW_FILE
echo "source \$RUN_SCRIPT \$JOBID" \$SHUTDOWN_MIN >> $RUN_WORKFLOW_FILE

