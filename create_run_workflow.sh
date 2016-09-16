#!/bin/bash
JOBID=$1
RUN_WORKFLOW_FILE=run_workflow.$JOBID.sh
SCRIPT_URL=https://raw.githubusercontent.com/hms-dbmi/tibanna/master/
echo "#!/bin/bash" > $RUN_WORKFLOW_FILE
echo "JOBID=$JOBID" >> $RUN_WORKFLOW_FILE
echo "RUN_SCRIPT=aws_run_workflow.sh" >> $RUN_WORKFLOW_FILE
echo "SCRIPT_URL=$SCRIPT_URL" >> $RUN_WORKFLOW_FILE
echo "wget \$SCRIPT_URL/\$RUN_SCRIPT" >> $RUN_WORKFLOW_FILE
echo "chmod +x \$RUN_SCRIPT" >> $RUN_WORKFLOW_FILE
echo "source \$RUN_SCRIPT \$JOBID" >> $RUN_WORKFLOW_FILE

