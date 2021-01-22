==========
Python API
==========


All the API functions are in the ``API`` class in ``tibanna.core``. Note that the class must be *instantiated* first (``API().run_workflow`` rather than ``API.run_workflow``).

General Usage

::

    from tibanna.core import API
    API().method(...)


Example

::

    from tibanna.core import API
    API().run_workflow(input_json='myrun.json')  # json file or dictionary object


Admin only commands
+++++++++++++++++++


The following commands require admin previlege to one's AWS account.

deploy_unicorn
--------------


To create an instance of tibanna unicorn (step function + lambdas)

::

    API().deploy_unicorn(...)


**Parameters**


::

  buckets=<bucket1,bucket2,...>       List of buckets as a string to use for tibanna runs.
                                      The associated lambda functions, EC2 instances
                                      and user group will be given permission to these buckets.

  no_setup                            Skip setup buckets/permissions and just redeploy tibanna
                                      step function and lambdas.
                                      This is useful when upgrading the existing tibanna that's
                                      already set up.

  no_setenv                           Do not overwrite TIBANNA_DEFAULT_STEP_FUNCTION_NAME
                                      environmental variable in your bashrc.

  suffix                              Using suffix helps deploying various dev-version tibanna.
                                      The step function and lambda functions will have the suffix.

  usergroup                           Tibanna usergroup to share the permission to access
                                      buckets and run jobs

  do_not_delete_public_access_block   If set True, Tibanna does not delete public
                                      access block from the specified buckets
                                      (this way postrunjson and metrics reports will
                                      not be public). Default False.


Note: starting ``0.9.0``, users do not need to export ``AWS_ACCOUNT_NUMBER`` and ``TIBANNA_AWS_REGION`` any more.


deploy_core
-----------

Deploy/update only a single lambda function

::

    API().deploy_core(name=<lambda_name>, ...)


where ``<lambda_name>`` would be either ``run_task_awsem`` or `check_task_awsem``.


**Options**


::

  suffix=<suffixname>            Using suffix helps deploying various dev-version tibanna.
                                 The step function and lambda functions will have the suffix.

  usergroup=<usergroup>          Tibanna usergroup to share the permission to access
                                 buckets and run jobs


users
-----

To list users

::

    API().users()


add_user
--------

To add users to a tibanna user group

::

    API().add_user(user=<user>, usegroup=<usergroup>)


cleanup
-------

To remove Tibanna components on AWS.

::

    API().cleanup(user_group_name=<usergroup>, ...)


**Options**


::

  suffix=<suffixname>            If suffix was used to deploy a tibanna, it should be added
                                 here. The step function and lambda functions will have the
                                 suffix at the end.

  ignore_errors=<True|False>     If True, if any of the components does not exist (e.g.
                                 already removed), it does not throw an error and keeps on
                                 to remove the other components. (default True)

  do_not_remove_iam_group<True|False>
                                 If True, does not remove the IAM permission. This option is
                                 recommended if various suffices are used to share the same
                                 usergroup. (default False)

  purge_history=<True|False>     If True, remove all the job logs and other job-related files
                                 from S3 bucket and dynamoDB. Please use with caution.
                                 (default False)

  verbose=<True|False>           Verbose if True. (default False)



setup_tibanna_env
-----------------

- Advanced user only

To set up environment on AWS without deploying tibanna, use `tibanna setup_tibanna_env`.


::

    API().setup_tibanna_env(...)


**Options**

::

  usergroup_tag=<usergrouptag>        an identifier for a usergroup that shares
                                      a tibanna permission

  no_randomize                        If set True, Tibanna does not add a random
                                      number to generate a usergroup name (e.g. the
                                      usergroup name used will be identical to the
                                      one specified using the ``usergrou_tag`` option.
                                      By default, a random number will be added at the
                                      end (e.g. default_2721). Default False.

  buckets=<bucket_list>               A comma-delimited list of bucket names - the
                                      buckets to which Tibanna needs access to
                                      through IAM role (input, output, log).

  do_not_delete_public_access_block   If set True, Tibanna does not delete public
                                      access block from the specified buckets
                                      (this way postrunjson and metrics reports will
                                      not be public). Default False.




Non-admin commands
++++++++++++++++++

The following commands can be used by a non-admin user, as long as the user belongs to the right user group.


run_workflow
------------

To run workflow

::

    API().run_workflow(input_json=<input_json_file|input_dict>, ...)


**Options**

::

  sfn=<stepfunctionname>         An example step function name may be
                                 'tibanna_unicorn_defaut_3978'. If not specified, default
                                 value is taken from environmental variable
                                 TIBANNA_DEFAULT_STEP_FUNCTION_NAME.
  jobid=<JOBID>                  specify a user-defined job id (randomly generated if
                                 not specified)
  open_browser=<True|False>      Open browser (default True)
  sleep=<SLEEP>                  Number of seconds between submission, to avoid drop-
                                 out (default 3)


run_batch_workflows
-------------------

To run multiple workflows in a batch. This command does not open browser and job ids are always automatically assigned.

::

    API().run_batch_workflows(input_json_list=<list_of_input_json_files_or_dicts>, ...)


**Options**

::

  sfn=<stepfunctionname>         An example step function name may be
                                 'tibanna_unicorn_defaut_3978'. If not specified, default
                                 value is taken from environmental variable
                                 TIBANNA_DEFAULT_STEP_FUNCTION_NAME.
  sleep=<SLEEP>                  Number of seconds between submission, to avoid drop-
                                 out (default 3)



stat
----

To check status of workflows,

::

    API().stat(...)


**Options**

::

  status=<status>                filter by run status (all runs if not specified).
                                 Status must be one of the following values:
                                 RUNNING|SUCCEEDED|FAILED|TIMED_OUT|ABORTED

  sfn=<stepfunctionname>         An example step function name may be
                                 'tibanna_unicorn_defaut_3978'. If not specified, default
                                 value is taken from environmental variable
                                 TIBANNA_DEFAULT_STEP_FUNCTION_NAME.

  n=<number_of_lines>            print out only the first n lines

  job_ids=<list_of_job_ids>      filter by a list of job ids


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

    API().log(exec_arn=<stepfunctionrun_arn>|job_id=<jobid>, ...)


**Options**

::

  postrunjson=<True|False>       The postrunjson option streams out a postrun json file instead of a log file.
                                 A postrun json file is available only after the run finishes.
                                 It contains the summary of the job including input, output, EC2 config and
                                 Cloudwatch metrics on memory/CPU/disk space.

  runjson=<True|False>           prints out run json instead, which is the json file tibanna sends to the instance
                                 before the run starts.

  top=<True|False>               prints out top file (log file containing top command output) instead. This top file
                                 contains all the top batch command output at a 1-minute interval.

  top_latest=<True|False>        prints out the latest content of the top file. This one contains only the latest
                                 top command output (latest 1-minute interval).


rerun
-----


To rerun a failed job with the same input json on a specific step function.

::

    API().rerun(exec_arn=<execution_arn>|job_id=<jobid>, sfn=<target_stepfunction_name>, ...)


**Options**

::

  instance_type=<instance_type>  Override instance type for the rerun

  shutdown_min=<shutdown_min>    Override shutdown minutes for the rerun

  ebs_size=<ebs_size>            Override EBS size for the rerun

  ebs_type=<ebs_size>            Override EBS type for the rerun

  ebs_iops=<ebs_iops>            Override EBS IOPS for the rerun

  key_name=<key_name>            Override key name for the rerun

  name=<run_name>                Override run name for the rerun

  appname_filter=<appname>       Rerun only if the app name matches the specified app name.


rerun_many
----------

To rerun many jobs that failed after a certain time point

::

    API().rerun_many(...)


**Options**

::

  sfn=<stepfunctionname>         An example step function name may be
                                 'tibanna_unicorn_defaut_3978'. If not specified, default
                                 value is taken from environmental variable
                                 TIBANNA_DEFAULT_STEP_FUNCTION_NAME.

  stopdate=<stopdate>            e.g. '14Feb2018'

  stophour=<stophour>            e.g. 14 (24-hour format, same as system time zone by default)

  stopminute=<stopminute>        e.g. 30 (default 0)

  sleeptime=<sleeptime>          seconds between reruns (eefault 5)

  offset=<offset>                offset between AWS time zone and system time zone (default 0)
                                 e.g. if 17:00 by AWS time zone corresponds to 12:00 by system
                                 time zone, offset must be 5.

  status=<status>                filter by status. default 'FAILED', i.e. rerun only failed
                                 jobs

  instance_type=<instance_type>  Override instance type for the rerun

  shutdown_min=<shutdown_min>    Override shutdown minutes for the rerun

  ebs_size=<ebs_size>            Override EBS size for the rerun

  ebs_type=<ebs_size>            Override EBS type for the rerun

  ebs_iops=<ebs_iops>            Override EBS IOPS for the rerun

  key_name=<key_name>            Override key name for the rerun

  name=<run_name>                Override run name for the rerun

  appname_filter=<appname>       Rerun only if the app name matches the specified app name.


**Example**

::

  API().rerun_many(stopdate='14Feb2018', stophour=15)


This example will rerun all the jobs of default step function that failed after 3pm on Feb 14 2018.


kill
----

To kill a specific job through its execution arn or a jobid

::

    API().kill(exec_arn=<execution_arn>)

or

::

    API().kill(job_id=<jobid>, sfn=<stepfunctionname>)


If ``jobid`` is specified but not ``stepfunctionname``, then by default it assumes ``TIBANNA_DEFAULT_STEP_FUNCTION_NAME``. If the job id is not found in the executions on the default or specified step function, then  only the EC2 instance will be terminated and the step function status may still be RUNNING.



**Example**

For example, let's say we run the following job by mistake.

::

    API().run_workflow(input_json='fastqc.json')


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

    API().kill(exec_arn='arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default3537:fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293')

or

::

   API().kill(job_id='jLeL6vMbhL63')



kill_all
--------

To kill all currently running jobs for a given step function

::

    API().kill_all(...)


**Options**

::

  sfn=<stepfunctionname>         An example step function name may be
                                 'tibanna_unicorn_defaut_3978'. If not specified, default
                                 value is taken from environmental variable
                                 TIBANNA_DEFAULT_STEP_FUNCTION_NAME.

list_sfns
---------

To list all step functions

::

    API().list_sfns(...)


**Options**

::

    n      show stats of the number of jobs for per status (using this option could slow down the
           process)


plot_metrics
------------

To collect, save and visualize the resources metrics from Cloud Watch

::

 API().plot_metrics(job_id=<jobid>, ...)

**Options**

::

 sfn=<stepfunctionname>             An example step function name may be
                                    'tibanna_unicorn_defaut_3978'. If not specified, default
                                    value is taken from environmental variable
                                    TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                    variable is not set, it uses name 'tibanna_pony' (4dn
                                    default, works only for 4dn).

 force_upload                       This flag force the upload of the metrics reports
                                    to the S3 bucket, even if there is a lock (upload
                                    is blocked by default by the lock)

 update_html_only                   This flag specify to only update the html file for
                                    metrics visualization,
                                    metrics reports are not updated

 open_browser                       This flag specify to not open the browser to visualize
                                    the metrics html after it has been created/updated

 filesystem=<filesystem>            Define the filesystem of the EC2 instance, default
                                    value is '/dev/nvme1n1'

 endtime=<endtime>                  End time of the interval to be considered
                                    to retrieve the data

 instance_id=<instance_id>          Manually provide instance ID in case Tibanna somehow
                                    can't find the information. This field is not required
                                    normally.


cost
----

To retrieve the cost and update the metrics report file created with plot_metrics

::

 API().cost(job_id=<jobid>, ...)

**Options**

::

 sfn=<stepfunctionname>             An example step function name may be
                                    'tibanna_unicorn_defaut_3978'. If not specified, default
                                    value is taken from environmental variable
                                    TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                    variable is not set, it uses name 'tibanna_pony' (4dn
                                    default, works only for 4dn).

 update_tsv                         This flag specify to update with cost the tsv file that
                                    stores metrics information on the S3 bucket

