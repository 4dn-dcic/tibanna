========
Commands
========


setup_tibanna_env
-----------------
To set up environment on AWS as admin, use `invoke setup_tibanna_env`.



deploy_tibanna
---------------

To deploy Tibanna, you need the following environmental variables set on your local machine from which you're deploying Tibanna.

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

To deploy lambda functions (use suffix for development version lambdas)

::
    
    # individual lambda functions
    invoke deploy_core <lambda_name> [--suffix=<suffixname>]
    # example <lambda_name> : run_task_awsem
    # example <suffixname> : dev
    
    # all lambda functions
    invoke deploy_core all [--suffix=<suffixname>]
    # example <suffixname> : dev



run_workflow
------------

To run workflow

::

    invoke run_workflow --input-json=<input_json_file> [--workflow=<stepfunctionname>]
    # <stepfunctionname> may be one of tibanna_pony, tibanna_unicorn or any tibanna step function name that was created by the create_workflow command.


For more detail, see https://github.com/4dn-dcic/tibanna/blob/master/tutorials/tibanna_unicorn.md#set-up-aws-cli



rerun
-----


To rerun a failed job with the same input json

::

    invoke rerun --exec-arn=<stepfunctionrun_arn> [--workflow=<stepfunctionname>]
    # <stepfunctionname> may be one of tibanna_pony, tibanna_unicorn or tibanna_pony-dev


rerun_many
----------

To rerun many jobs that failed after a certain time point

::
    
    invoke rerun_many [--workflow=<stepfunctionname>] \
                      [--stopdate=<stopdate>] \
                      [--stophour=<stophour>] \
                      [--stopminute=<stopminute>] \
                      [--sleeptime=<sleeptime>] \
                      [--offset=<offset>] \
                      [--status=<status>]
    # <stepfunctionname> may be one of tibanna_pony (default), tibanna_unicorn or tibanna_pony-dev
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

    invoke kill_all [--workflow=<stepfunctionname>]


