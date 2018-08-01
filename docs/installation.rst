============
Installation
============

Dependency
----------

- Python 2.7
- Pip 9.0.3 / 10.0.1
- The other dependencies are listed in requirements.txt and are auto-installed in the following steps.
- If you are 4DN-DCIC user, use the dependencies specified in requirements-4dn.txt. These include all the base requirements in requirements.txt, as well as other 4DN-specific pakages.


Admin
-----

As admin, you need to first set up Tibanna environment on your AWS account and create a usergroup with a shared permission to the environment.

::

    # install tibanna package
    virtualenv -p python2.7 ~/venv/tibanna
    source ~/venv/tibanna/bin/activate
    
    # install pip 9.0.3 (or 10.0.1)
    python -m pip install pip==9.0.3  # or curl https://bootstrap.pypa.io/get-pip.py | python - 'pip==9.0.3'
    
    git clone https://github.com/4dn-dcic/tibanna
    cd tibanna
    pip install -r requirements.txt  # if you're 4dn-dcic, use requirements-4dn.txt instead

Set up awscli: for more details see https://github.com/4dn-dcic/tibanna/blob/master/tutorials/tibanna_unicorn.md#set-up-aws-cli

To set up and deploy Tibanna, you need the following environmental variables set and exported on your local machine from which you're setting up/deploying Tibanna.

::

    export TIBANNA_AWS_REGION=<aws_region>  # (e.g. us-east-1)
    export AWS_ACCOUNT_NUMBER=<aws account number>


If you're using a forked repo or want to use a specific branch set the following variables accordingly and export them. If you're using default (4dn-dcic/tibanna, master), no need to set these variables.

::

    export TIBANNA_REPO_NAME=4dn-dcic/tibanna
    export TIBANNA_REPO_BRANCH=master

Then, set up user group and permission on AWS by using invoke setup_tibanna_env.

::

    invoke setup_tibanna_env --buckets=<bucket1>,<bucket2>,...   # add all the buckets your input/output files and log files will go to. The buckets must already exist.


As an example,

::

    invoke setup_tibanna_env --buckets=my-tibanna-test-bucket,my-tibanna-test-input-bucket (the public has permission to these buckets - the objects will expire in 1 day and others may have access to the same bucket and read/overwrite/delete your objects. Use it only for testing Tibanna.)


If you're 4DN-DCIC, you could do the following.

::

    invoke setup_tibanna_env --buckets=elasticbeanstalk-fourfront-webdev-files,elasticbeanstalk-fourfront-webdev-wfoutput,tibanna-output,4dn-aws-pipeline-run-json  # this is for 4dn-dcic. (the public does not have permission to these buckets)


The setup_tibanna_env command will create a usergroup that shares the permission to use a single tibanna environment. Multiple users can be added to this usergroup and multiple tibanna instances (step functions / lambdas) can be deployed. The usergroup created will be printed out on the screen after the command. (e.g. as below).

::

    Tibanna usergroup default_6206 has been created on AWS.


Then, deploy tibanna (unicorn) to your aws account for a specific user group (for more details about tibanna deployment, see below)

- Note: you can only use unicorn (the core with no communication with 4DN portal). Pony is reserved for 4DN-DCIC.

::

    invoke deploy_tibanna --usergroup=<usergroup> --sfn-type=unicorn


As an exmple,

::

    invoke deploy_tibanna --usergroup=default_6206 --sfn-type=unicorn

To run a workflow on the tibanna (unicorn) deployed for the usergroup (for more details about running workflows, see below),

::

    invoke run_workflow --workflow=tibanna_unicorn_<usergroup> --input-json=<input_json_for_a_workflow_run>

As an example you can try to run a test workflow as below.

invoke run_workflow --workflow=tibanna_unicorn_default_6206 --input-json=test_json/my_test_tibanna_bucket.json
Then, add users to the usergroup.


User
----

As a user, you need to set up your awscli. You can only use run_workflow and you don't have permission to setup or deploy tibanna.

::

    virtualenv -p python2.7 ~/venv/tibanna
    source ~/venv/tibanna/bin/activate
    
    # pip 9.0.3 or 10.0.1
    python -m pip install pip==9.0.3  # or curl https://bootstrap.pypa.io/get-pip.py | python - 'pip==9.0.3'
    git clone https://github.com/4dn-dcic/tibanna
    cd tibanna
    pip install -r requirements.txt

Set up awscli: for more details see https://github.com/4dn-dcic/tibanna/blob/master/tutorials/tibanna_unicorn.md#set-up-aws-cli

To run workflow on the tibanna (unicorn) deployed for the usergroup (for more details about running workflows, see below)

::

    invoke run_workflow --workflow=tibanna_unicorn_<usergroup> --input-json=<input_json_for_a_workflow_run>

As an example,

::

    invoke run_workflow --workflow=tibanna_unicorn_default_6206 --input-json=test_json/my_test_tibanna_bucket.json

For more details, see Tutorials/tibanna_unicorn.md


