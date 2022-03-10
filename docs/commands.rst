==================
Command-line tools
==================

Listing all commands
++++++++++++++++++++

To list all available commands, use ``tibanna -h``

::

    tibanna -h


Checking Tibanna version
++++++++++++++++++++++++

To check Tibanna version,


::

    tibanna -v


Admin only commands
+++++++++++++++++++

The following commands require admin previlege to one's AWS account.

deploy_unicorn
--------------


To create an instance of tibanna unicorn (step function + lambdas)

::

    tibanna deploy_unicorn [<options>]


**Options**


::

  -b|--buckets=<bucket1,bucket2,...>       List of buckets to use for tibanna runs.
                                           The associated lambda functions, EC2
                                           instances and user group will be given
                                           permission to these buckets.

  -S|--no-setup                            Skip setup buckets/permissions and just
                                           redeploy tibanna step function and lambdas.
                                           This is useful when upgrading the existing
                                           tibanna that's already set up.

  -E|--no-setenv                           Do not overwrite TIBANNA_DEFAULT_STEP_FUNCTION_NAME
                                           environmental variable in your bashrc.

  -s|--suffix=<suffixname>                 Using suffix helps deploying various dev-version
                                           tibanna. The step function and lambda functions
                                           will have the suffix. Having a different suffix
                                           does not create a new user group with a different
                                           permission (for this purpose use --usergroup).

  -g|--usergroup=<usergroup>               Tibanna usergroup to share the permission to access
                                           buckets and run jobs

  -P|--do-not-delete-public-access-block   Do not delete public access block from buckets
                                           (this way postrunjson and metrics reports will
                                           not be public)

-C|--deploy-costupdater                    Deploys an additional step function that will periodically 
                                           check, if the cost for a workflow run can be retrieved from AWS.
                                           If it is available, it will automatically update the
                                           metrics report.


Note: starting ``0.9.0``, users do not need to export ``AWS_ACCOUNT_NUMBER`` and ``TIBANNA_AWS_REGION`` any more.


deploy_core
-----------

Deploy/update only a single lambda function

::

    tibanna deploy_core -n <lambda_name> [<options>]


where ``<lambda_name>`` would be either ``run_task_awsem`` or `check_task_awsem``.


**Options**


::

  -s|--suffix=<suffixname>            Using suffix helps deploying various dev-version tibanna.
                                      The step function and lambda functions will have the suffix.

  -g|--usergroup=<usergroup>          Tibanna usergroup to share the permission to access
                                      buckets and run jobs


users
-----

To list users

::

    tibanna users


add_user
--------

To add users to a tibanna user group

::

    tibanna add_user -u <user> -g <usergroup>



cleanup
-------

To remove Tibanna components on AWS.

::

    tibanna cleanup -g <usergroup> ... 


**Options**


::


  -s|--suffix=<suffixname>            If suffix was used to deploy a tibanna, it should be added
                                      here. The step function and lambda functions will have the
                                      suffix at the end.

  -E|--do-not-ignore-errors           By default, if any of the components does not exist (e.g.
                                      already removed), it does not throw an error and keeps on
                                      to remove the other components. Using this option turns off
                                      this feature and will throw an error.

  -G|--do-not-remove-iam-group        if set, it does not remove the IAM permissions. This option
                                      is recommended if various suffices are used to share the
                                      same usergroup.

  -p|--purge-history                  if set, remove all the job logs and other job-related files
                                      from S3 bucket and dynamoDB. Please use with caution.

  -q|--quiet                          run quietly




setup_tibanna_env
-----------------

- Advanced user only

To set up environment on AWS without deploying tibanna, use `tibanna setup_tibanna_env`.


::

    tibanna setup_tibanna_env <options>


**Options**

::

  -g|--usergroup-tag=<usergrouptag>        an identifier for a usergroup that shares
                                           a tibanna permission

  -R|--no-randomize                        do not add a random number to generate a
                                           usergroup name (e.g. the usergroup name used
                                           will be identical to the one specified using
                                           the ``--usergrou-tag`` option.  By default,
                                           a random number will be added at the end
                                           (e.g. default_2721).

  -b|--buckets=<bucket_list>               A comma-delimited list of bucket names - the
                                           buckets to which Tibanna needs access to
                                           through IAM role (input, output, log).

  -P|--do-not-delete-public-access-block   Do not delete public access block from buckets
                                           (this way postrunjson and metrics reports will
                                           not be public)



Non-admin user commands
+++++++++++++++++++++++

The following commands can be used by a non-admin user, as long as the user belongs to the right user group.


run_workflow
------------

To run workflow

::

    tibanna run_workflow --input-json=<input_json_file> [<options>]

**Options**

::

  -s|--sfn=<stepfunctionname>         An example step function name may be
                                      'tibanna_unicorn_defaut_3978'. If not specified, default
                                      value is taken from environmental variable
                                      TIBANNA_DEFAULT_STEP_FUNCTION_NAME.
  -j JOBID, --jobid JOBID             specify a user-defined job id (randomly generated if
                                      not specified)
  -B, --do-not-open-browser           Do not open browser
  -S SLEEP, --sleep SLEEP             Number of seconds between submission, to avoid drop-
                                      out (default 3)


run_batch_workflows
-------------------

To run multiple workflows in a batch. This command does not open browser and job ids are
always automatically assigned. This function is available for Tibanna versions >= ``1.0.0``.

::

    tibanna run_batch_workflows -i <input_json_file> [<input_json_file2>] [...] [<options>]

**Options**

::

  -s|--sfn=<stepfunctionname>         An example step function name may be
                                      'tibanna_unicorn_defaut_3978'. If not specified, default
                                      value is taken from environmental variable
                                      TIBANNA_DEFAULT_STEP_FUNCTION_NAME.
  -S SLEEP, --sleep SLEEP             Number of seconds between submission, to avoid drop-
                                      out (default 3)



stat
----

To check status of workflows,

::

    tibanna stat [<options>]


**Options**

::

  -t|--status=<status>                  filter by run status (all runs if not specified).
                                        Status must be one of the following values:
                                        RUNNING|SUCCEEDED|FAILED|TIMED_OUT|ABORTED

  -s|--sfn=<stepfunctionname>           An example step function name may be
                                        'tibanna_unicorn_defaut_3978'. If not specified, default
                                        value is taken from environmental variable
                                        TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                        variable is not set, it uses name 'tibanna_pony' (4dn
                                        default, works only for 4dn).

  -n|--nlines=<number_of_lines>         print out only the first n lines

  -j|--job-ids <job_id> [<job_id2>] ... job ids of the specific jobs to display, separated by
                                        space. This option cannot be combined with
                                        --nlines(-n), --status(-t) or --sfn(-s). This option is
                                        available only for version >= ``1.0.0``.


The output is a table (an example below)

::

    jobid	status	name	start_time	stop_time
    2xPih7reR6FM	RUNNING md5	2018-08-15 17:45	2018-08-15 17:50
    3hbkJB3hv92S	SUCCEEDED	hicprocessingbam	2018-08-15 16:04	2018-08-15 16:09
    UlkvH3gbBBA2	FAILED	repliseq-parta	2018-08-09 18:26	2018-08-09 19:01
    j7hvisheBV27	SUCCEEDED	bwa-mem	2018-08-09 18:44	2018-08-09 18:59


log
---

To check the log or postrun json (summary) of a workflow run

::

    tibanna log --exec-arn=<stepfunctionrun_arn>|--job-id=<jobid> [<options>]

or

::

    tibanna log --exec-name=<exec_name> --sfn=<stepfunctionname> [<options>]


**Options**

::

  -p|--postrunjson      The -p option streams out a postrun json file instead of a log file.
                        A postrun json file is available only after the run finishes.
                        It contains the summary of the job including input, output, EC2 config and
                        Cloudwatch metrics on memory/CPU/disk space.

  -r|--runjson          print out run json instead, which is the json file tibanna sends to the instance
                        before the run starts. (new in ``1.0.0``)

  -t|--top              prints out top file (log file containing top command
                        output) instead. This top file contains all the top batch command output
                        at a 1-minute interval. (new in ``1.0.0``)

  -T|--top-latest       prints out the latest content of the top file. This one contains only the latest
                        top command output (latest 1-minute interval). (new in ``1.0.0``)


rerun
-----


To rerun a failed job with the same input json on a specific step function.

::

    tibanna rerun --exec-arn=<execution_arn>|--job-id=<jobid> --sfn=<target_stepfunction_name> [<options>]


**Options**

::

  -i|--instance-type=<instance_type>  Override instance type for the rerun

  -d|--shutdown-min=<shutdown_min>    Override shutdown minutes for the rerun

  -b|--ebs-size=<ebs_size>            Override EBS size for the rerun

  -T|--ebs-type=<ebs_size>            Override EBS type for the rerun

  -p|--ebs-iops=<ebs_iops>            Override EBS IOPS for the rerun

  -k|--key-name=<key_name>            Override key name for the rerun

  -n|--name=<run_name>                Override run name for the rerun

  -a|--appname-filter=<appname>       Rerun only if the app name matches the specified app name.


rerun_many
----------

To rerun many jobs that failed after a certain time point

::

    tibanna rerun_many [<options>]


**Options**

::

  -s|--sfn=<stepfunctionname>         An example step function name may be
                                      'tibanna_unicorn_defaut_3978'. If not specified, default
                                      value is taken from environmental variable
                                      TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                      variable is not set, it uses name 'tibanna_pony' (4dn
                                      default, works only for 4dn).

  -D|--stopdate=<stopdate>            e.g. '14Feb2018'

  -H|--stophour=<stophour>            e.g. 14 (24-hour format, same as system time zone by default)

  -M|--stopminute=<stopminute>        e.g. 30 (default 0)

  -r|--sleeptime=<sleeptime>          seconds between reruns (eefault 5)

  -o|--offset=<offset>                offset between AWS time zone and system time zone (default 0)
                                      e.g. if 17:00 by AWS time zone corresponds to 12:00 by system
                                      time zone, offset must be 5.

  -t|--status=<status>                filter by status. default 'FAILED', i.e. rerun only failed
                                      jobs

  -i|--instance-type=<instance_type>  Override instance type for the rerun

  -d|--shutdown-min=<shutdown_min>    Override shutdown minutes for the rerun

  -b|--ebs-size=<ebs_size>            Override EBS size for the rerun

  -T|--ebs-type=<ebs_size>            Override EBS type for the rerun

  -p|--ebs-iops=<ebs_iops>            Override EBS IOPS for the rerun

  -k|--key-name=<key_name>            Override key name for the rerun

  -n|--name=<run_name>                Override run name for the rerun

  -a|--appname-filter=<appname>       Rerun only if the app name matches the specified app name.


**Example**

::

  tibanna rerun_many --stopdate=14Feb2018 --stophour=15


This example will rerun all the jobs of default step function that failed after 3pm on Feb 14 2018.


kill
----

To kill a specific job through its execution arn or a jobid

::

    tibanna kill --exec-arn=<execution_arn>|--job-id=<jobid>


If the execution id or job id is not found in the current RUNNING executions (e.g. the execution has already been aborted), then  only the EC2 instance will be terminated.



**Example**

For example, let's say we run the following job by mistake.

::

    $ tibanna run_workflow --input-json=fastqc.json

The following message is printed out

::

    about to start run fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293
    response from aws was:
    {u'startDate': datetime.datetime(2018, 10, 11, 20, 15, 0, 71000, tzinfo=tzlocal()), 'ResponseMetadata': {'RetryAttempts': 0, 'HTTPStatusCode': 200, 'RequestId': '54664dcc-cd92-11e8-a2c0-51ce6ca6c6ea', 'HTTPHeaders': {'x-amzn-requestid': '54664dcc-cd92-11e8-a2c0-51ce6ca6c6ea', 'content-length': '161', 'content-type': 'application/x-amz-json-1.0'}}, u'executionArn': u'arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default3537:fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293'}
    url to view status:
    https://console.aws.amazon.com/states/home?region=us-east-1#/executions/details/arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default3537:fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293
    JOBID jLeL6vMbhL63 submitted
    EXECUTION ARN = arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default3537:fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293


To kill this job, use the execution arn in the above message ('EXECUTION_ARN') (it can also be found on the Step Function Console)


::

    $ tibanna kill --exec-arn=arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default3537:fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293

or

::

    $ tibanna kill --job-id jLeL6vMbhL63



kill_all
--------

To kill all currently running jobs for a given step function

::

    tibanna kill_all


**Options**

::

  -s|--sfn=<stepfunctionname>         An example step function name may be
                                      'tibanna_unicorn_defaut_3978'. If not specified, default
                                      value is taken from environmental variable
                                      TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                      variable is not set, it uses name 'tibanna_pony' (4dn
                                      default, works only for 4dn).

list_sfns
---------

To list all step functions

::

    tibanna list_sfns [-n]

**Options**

::

    -n      show stats of the number of jobs for per status (using this option could slow down the
            process)

plot_metrics
------------

To collect, save and visualize the resources metrics from Cloud Watch

::

  tibanna plot_metrics --job-id=<jobid> [<options>]

**Options**

::

  -s|--sfn=<stepfunctionname>         An example step function name may be
                                      'tibanna_unicorn_defaut_3978'. If not specified, default
                                      value is taken from environmental variable
                                      TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                      variable is not set, it uses name 'tibanna_pony' (4dn
                                      default, works only for 4dn).

  -f|--force-upload                   This flag force the upload of the metrics reports
                                      to the S3 bucket, even if there is a lock (upload
                                      is blocked by default by the lock)

  -u|--update-html-only               This flag specify to only update the html file
                                      for metrics visualization,
                                      metrics reports are not updated

  -B|--do-not-open-browser            Do not open the browser to visualize the metrics html
                                      after it has been created/updated

  -i|--instance-id=<instance_id>      Manually provide instance ID in case Tibanna somehow
                                      can't find the information. This field is not required normally.
  

cost
----

To retrieve the cost and update the metrics report file created with plot_metrics. The cost is typically available 24 hours after the job finished.
This function is available to non-admin users from version 1.0.6.

::

 tibanna cost --job-id=<jobid> [<options>]

**Options**

::

 -s|--sfn=<stepfunctionname>         An example step function name may be
                                     'tibanna_unicorn_defaut_3978'. If not specified, default
                                     value is taken from environmental variable
                                     TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                     variable is not set, it uses name 'tibanna_pony' (4dn
                                     default, works only for 4dn).

 -u|--update-tsv                     Update with the cost the tsv file that stores metrics
                                     information on the S3 bucket

cost_estimate
-------------

To retrieve cost estimates and update the metrics report file created with plot_metrics. In contrast to the exact costs, the estimated costs are available immediately after the job has completed.
The cost estimate will also indicate if it is an immediate estimate (i.e., the exact cost is not yet available), the actual cost or the retrospective estimate (i.e., the exact cost is not available anymore). In case the estimate returns the actual cost and the `-u` parameter is set, the cost row in the metrics file will be automatically updated.
This function requires a (deployed) Tibanna version >=1.0.6.

::

 tibanna cost_estimate --job-id=<jobid> [<options>]

**Options**

::

 -u|--update-tsv                     Update with the cost the tsv file that stores metrics
                                     information on the S3 bucket

 -f|--force                          Return the estimate, even if the actual cost is available


