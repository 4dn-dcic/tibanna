============
Installation
============


Installing Tibanna package
--------------------------

Tibanna works with the following Python and pip versions.

- Python 2.7
- Pip 9.0.3 / 10.0.1


Install Tibanna on your local machine or server from which you want to send commands to run workflows.

::

    # create a virtual environment with pip 9.0.3 (or 10.0.1)
    virtualenv -p python2.7 ~/venv/tibanna
    source ~/venv/tibanna/bin/activate
    python -m pip install pip==9.0.3  # or curl https://bootstrap.pypa.io/get-pip.py | python - 'pip==9.0.3'
  
  
::

    # installing tibanna package
    git clone https://github.com/4dn-dcic/tibanna
    cd tibanna
    pip install -r requirements.txt  # if you're 4dn-dcic, use requirements-4dn.txt instead


Alternatively, use ``setup.py``

::

   # installing tibanna package
    git clone https://github.com/4dn-dcic/tibanna
    cd tibanna
    python setup.py install


Deploying Tibanna to AWS
------------------------

To set up and deploy Tibanna, you need an AWS account and the following environmental variables set and exported on your local machine.

::

    export AWS_ACCOUNT_NUMBER=<your_12_digit_aws_account_number>
    export TIBANNA_AWS_REGION=<aws_region>  # (e.g. us-east-1)


If you're using a forked repo or want to use a specific branch set the following variables as well. They will be used by the EC2 (VM) instances to grab the right scripts from the `awsf` directory of the right tibanna repo/branch. If you're using default (4dn-dcic/tibanna, master), no need to set these variables.

::

    export TIBANNA_REPO_NAME=<git_hub_repo_name>  # (default: 4dn-dcic/tibanna)
    export TIBANNA_REPO_BRANCH=<git_hub_branch_name>  # (default: master)


Then, set up buckets and user group permission for Tibanna as below.

::

    invoke deploy_unicorn --buckets=<bucket1>,<bucket2>,...
    # add all the buckets your input/output files and log files will go to. The buckets must already exist.


The above command will first create a usergroup that shares the permission to use a single tibanna environment. Then, it will deploy a tibanna instance (step function / lambda). The name of the tibanna step function is added to your ``~/.bashrc`` file. Check that you can see the following line in the ``~/.bashrc`` file.

::

    export TIBANNA_DEFAULT_STEP_FUNCTION_NAME=tibanna_unicorn_<usergroup_name>


To set this environmental variable,

::

    source ~/.bashrc


You can run a workflow using Tibanna if you're an admin user or if you are a user that belongs to the user group.

::

    invoke run_workflow --input-json=<input_json_for_a_workflow_run>


Example
-------

Let's try setting up Tibanna that uses public buckets ``my-tibanna-test-bucket`` and ``my-tibanna-test-input-bucket``. The public has permission to these buckets - the objects will expire in 1 day and others may have access to the same bucket and read/overwrite/delete your objects. Please use it only for initial testing of Tibanna.

::

    invoke deploy_unicorn --buckets=my-tibanna-test-bucket,my-tibanna-test-input-bucket


Export the environmental variable for Tibanna step function name.

::

    source ~/.bashrc


As an example you can try to run a test workflow as below.

::

    invoke run_workflow --input-json=test_json/unicorn/my_test_tibanna_bucket.json

