==================
Command-line tools
==================


Basic_commands
++++++++++++++

deploy_unicorn
--------------


To create an instance of tibanna unicorn (step function + lambdas)

::

    invoke deploy_unicorn [<options>]


**Options**


::

  --buckets=<bucket1,bucket2,...>  List of buckets to use for tibanna runs.
                                   The associated lambda functions, EC2 instances
                                   and user group will be given permission to these buckets.

  --no-setup                       Skip setup buckets/permissions and just redeploy tibanna
                                   step function and lambdas.
                                   This is useful when upgrading the existing tibanna that's
                                   already set up.

  --no-setenv                      Do not overwrite TIBANNA_DEFAULT_STEP_FUNCTION_NAME
                                   environmental variable in your bashrc.

  --suffix=<suffixname>            Using suffix helps deploying various dev-version tibanna.
                                   The step function and lambda functions will have the suffix.



To deploy Tibanna unicorn, you need the following environmental variables set on your local machine from which you're deploying Tibanna.

::

    export TIBANNA_AWS_REGION=<aws_region>  # (e.g. us-east-1)
    export AWS_ACCOUNT_NUMBER=<aws_account_number>



run_workflow
------------

To run workflow

::

    invoke run_workflow --input-json=<input_json_file> [<options>]

**Options**

::

  --sfn=<stepfunctionname>         An example step function name may be
                                   'tibanna_unicorn_defaut_3978'. If not specified, default
                                   value is taken from environmental variable
                                   TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                   variable is not set, it uses name 'tibanna_pony' (4dn
                                   default, works only for 4dn).



stat
----

To check status of workflows,

::

    invoke stat [<options>]


**Options**

::

  --status=<status>                filter by run status (all runs if not specified).
                                   Status must be one of the following values:
                                   RUNNING|SUCCEEDED|FAILED|TIMED_OUT|ABORTED

  --sfn=<stepfunctionname>         An example step function name may be
                                   'tibanna_unicorn_defaut_3978'. If not specified, default
                                   value is taken from environmental variable
                                   TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                   variable is not set, it uses name 'tibanna_pony' (4dn
                                   default, works only for 4dn).


The output is a table (an example below)

::

    jobid	status	name	start_time	stop_time
    2xPih7reR6FM	RUNNING md5	2018-08-15 17:45	2018-08-15 17:50
    3hbkJB3hv92S	SUCCEEDED	hicprocessingbam	2018-08-15 16:04	2018-08-15 16:09
    UlkvH3gbBBA2	FAILED	repliseq-parta	2018-08-09 18:26	2018-08-09 19:01
    j7hvisheBV27	SUCCEEDED	bwa-mem	2018-08-09 18:44	2018-08-09 18:59


rerun
-----


To rerun a failed job with the same input json

::

    invoke rerun --exec-arn=<stepfunctionrun_arn> [<options>]


**Options**

::

  --sfn=<stepfunctionname>         An example step function name may be
                                   'tibanna_unicorn_defaut_3978'. If not specified, default
                                   value is taken from environmental variable
                                   TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                   variable is not set, it uses name 'tibanna_pony' (4dn
                                   default, works only for 4dn).


rerun_many
----------

To rerun many jobs that failed after a certain time point

::
    
    invoke rerun_many [<options>]
    

**Options**

::

  --sfn=<stepfunctionname>         An example step function name may be
                                   'tibanna_unicorn_defaut_3978'. If not specified, default
                                   value is taken from environmental variable
                                   TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                   variable is not set, it uses name 'tibanna_pony' (4dn
                                   default, works only for 4dn).

  --stopdate=<stopdate>            e.g. '14Feb2018'

  --stophour=<stophour>            e.g. 14 (24-hour format, same as system time zone by default)

  --stopminute=<stopminute>        e.g. 30 (default 0)

  --sleeptime=<sleeptime>          seconds between reruns (eefault 5)

  --offset=<offset>                offset between AWS time zone and system time zone (default 0)
                                   e.g. if 17:00 by AWS time zone corresponds to 12:00 by system
                                   time zone, offset must be 5.

  --status=<status>                 filter by status. default 'FAILED', i.e. rerun only failed
                                   jobs


**Example** 

::

  invoke rerun_many --stopdate=14Feb2018 --stophour=15


This example will rerun all the jobs of default step function that failed after 3pm on Feb 14 2018.


kill
----

To kill a specific job through its execution arn

::

    invoke kill --exec-arn=<execution_arn>

**Example**

For example, let's say we run the following job by mistake.

::

    $ invoke run_workflow --input-json=fastqc.json

The following message is printed out

::

    about to start run fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293
    response from aws was: 
    {u'startDate': datetime.datetime(2018, 10, 11, 20, 15, 0, 71000, tzinfo=tzlocal()), 'ResponseMetadata': {'RetryAttempts': 0, 'HTTPStatusCode': 200, 'RequestId': '54664dcc-cd92-11e8-a2c0-51ce6ca6c6ea', 'HTTPHeaders': {'x-amzn-requestid': '54664dcc-cd92-11e8-a2c0-51ce6ca6c6ea', 'content-length': '161', 'content-type': 'application/x-amz-json-1.0'}}, u'executionArn': u'arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default3537:fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293'}
    url to view status:
    https://console.aws.amazon.com/states/home?region=us-east-1#/executions/details/arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default3537:fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293
    JOBID jLeL6vMbhL63 submitted
    EXECUTION ARN = arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default3537:fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293
    Couldn't get a file descriptor referring to the console


To kill this job, use the execution arn in the above message ('EXECUTION_ARN') (it can also be found on the Step Function Console)


::

    $ invoke kill --exec-arn=arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default3537:fastqc_85ba7f41-daf5-4f82-946f-06d31d0cd293



kill_all
--------

To kill all currently running jobs for a given step function

::

    invoke kill_all --sfn=<stepfunctionname>

**Options**

::

  --sfn=<stepfunctionname>         An example step function name may be
                                   'tibanna_unicorn_defaut_3978'. If not specified, default
                                   value is taken from environmental variable
                                   TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                   variable is not set, it uses name 'tibanna_pony' (4dn
                                   default, works only for 4dn).


Advanced_commands
+++++++++++++++++


setup_tibanna_env
-----------------

- Advanced user only

To set up environment on AWS without deploying tibanna, use `invoke setup_tibanna_env`.



deploy_tibanna
--------------

- Advanced user only

This function deploys either Tibanna unicorn or tibanna pony (default pony).
You need the following environmental variables set on your local machine from which you're deploying Tibanna.

::

    export TIBANNA_AWS_REGION=<aws_region>  # (e.g. us-east-1)
    export AWS_ACCOUNT_NUMBER=<aws_account_number>


If you're 4DN-DCIC and using Tibanna Pony, you need the additional environmental variables

::

    export SECRET=<fourfront_aws_secret_key>

To create an instance of tibanna (step function + lambdas)

::

    invoke deploy_tibanna [--suffix=<suffixname>] [--sfn_type=<sfn_type>] [--usergroup=<usergroup>] [--tests]
    # (use suffix for development version)
    # example <suffixname> : dev
    # <sfn_type> (step function type) is either 'pony' or 'unicorn' (default pony)
    # <usergroup> : a AWS user group that share permission to tibanna and the associated buckets given by the `invoke setup_tibanna_env` command..


example

::

    invoke deploy_tibanna --suffix=dev2


The above command will create a step function named tibanna_pony_dev2 that uses a set of lambdas with suffix _dev2, and deploys these lambdas.

example 2

::

    invoke deploy_tibanna --suffix=dev --sfn_type=unicorn

This example creates a step function named tibanna_unicorn_dev that uses a set of lambdas with suffix _dev, and deploys these lambdas. Using the --tests argument will ensure tests pass befor deploying; currently this is NOT available for users outside of 4DN-DCIC.


deploy_core
-----------

- Advanced user only

To deploy only lambda functions without deploying the step function (use suffix for development version lambdas)

::
    
    # individual lambda functions
    invoke deploy_core <lambda_name> [--suffix=<suffixname>]
    # example <lambda_name> : run_task_awsem
    # example <suffixname> : dev
    
    # all lambda functions
    invoke deploy_core all [--suffix=<suffixname>]
    # example <suffixname> : dev




test
----

- Advanced user only

Running tests on the current repo

::

    invoke test [--no-flake] [--ignore-pony] [--ignore-webdev]
    
    # --no-flake : skip flake8 test

For Unicorn-only tests,

::

    invoke test --ignore-pony

For full test including Pony and Webdev tests (4DN-dcic-only)

::

    invoke test [--no-flake]


