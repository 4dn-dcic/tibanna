==================
Command-line tools
==================


Basic_commands
++++++++++++++

deploy_unicorn
--------------


To create an instance of tibanna unicorn (step function + lambdas)

::

    invoke deploy_unicorn [--suffix=<suffixname>]
    # (use suffix for development version)
    # example <suffixname> : dev


**Options**

:---buckets=<bucket1,bucket2,...>    
                                     List of buckets to use for tibanna runs.
                                     The associated lambda functions, EC2 instances
                                     and user group will be given permission to these buckets.
:---no_setup                         
                                     Skip setup buckets/permissions and just redeploy tibanna
                                     step function and lambdas.
                                     This is useful when upgrading the existing tibanna that's
                                     already set up.
:---no_setenv                        
                                     Do not overwrite TIBANNA_DEFAULT_STEP_FUNCTION_NAME
                                     environmental variable in your bashrc.
:---suffix=<suffixname>              
                                     Using suffix helps deploying various dev-version tibanna.
                                     The step function and lambda functions will have the suffix.



To deploy Tibanna unicorn, you need the following environmental variables set on your local machine from which you're deploying Tibanna.

::

    TIBANNA_AWS_REGION  # aws region (e.g. us-east-1)
    AWS_ACCOUNT_NUMBER  # aws account number



run_workflow
------------

To run workflow

::

    invoke run_workflow --input-json=<input_json_file> [--sfn=<stepfunctionname>]

``<stepfunctionname>`` may be one of tibanna_pony, tibanna_unicorn or tibanna_pony-dev, etc. If not specified, default value is taken from environmental variable TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental variable is not set, it uses name 'tibanna_pony'.



stat
----

To check status of workflows,

::

    invoke stat [--sfn=<stepfunctioname>] [--status=RUNNING|SUCCEEDED|FAILED|TIMED_OUT|ABORTED]


``<stepfunctionname>`` may be one of tibanna_pony, tibanna_unicorn or tibanna_pony-dev, etc. If not specified, default value is taken from environmental variable TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental variable is not set, it uses name 'tibanna_pony'.


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

    invoke rerun --exec-arn=<stepfunctionrun_arn> [--sfn=<stepfunctionname>]
    # <stepfunctionname> may be one of tibanna_pony, tibanna_unicorn or tibanna_pony-dev, etc. If not specified, default value is taken from environmental variable TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental variable is not set, it uses name 'tibanna_pony'.


rerun_many
----------

To rerun many jobs that failed after a certain time point

::
    
    invoke rerun_many [--sfn=<stepfunctionname>] \
                      [--stopdate=<stopdate>] \
                      [--stophour=<stophour>] \
                      [--stopminute=<stopminute>] \
                      [--sleeptime=<sleeptime>] \
                      [--offset=<offset>] \
                      [--status=<status>]
    # <stepfunctionname> may be one of tibanna_pony, tibanna_unicorn or tibanna_pony-dev, etc. If not specified, default value is taken from environmental variable TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental variable is not set, it uses name 'tibanna_pony'.
    # <stopdate> e.g. '14Feb2018'
    # <stophour> e.g. 14 (24-hour format, EST by default, the time zone can be changed using --offset)
    # <stopminute> e.g. 30 (default 0)
    # <sleeptime> seconds between reruns (eefault 5)
    # <offset> offset for hour (for a different time zone) (default 5, consistent with EST)
    # <status> default 'FAILED', to collect and rerun only failed jobs
    
    # example: invoke rerun_many --stopdate=14Feb2018 --stophour=15
    # This example will rerun all failed jobs of tibanna_pony step function that failed after 3pm EST on Feb 14 2018.


kill_all
--------

To kill all currently running jobs (killing only step functions not the EC2 instances)

::

    invoke kill_all [--sfn=<stepfunctionname>]
    # <stepfunctionname> may be one of tibanna_pony, tibanna_unicorn or tibanna_pony-dev, etc. If not specified, default value is taken from environmental variable TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental variable is not set, it uses name 'tibanna_pony'.



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

    TIBANNA_AWS_REGION  # aws region (e.g. us-east-1)
    AWS_ACCOUNT_NUMBER  # aws account number


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


