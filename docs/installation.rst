============
Installation
============

Tibanna's installation is two-step. 

1. The python package content of the repo must be installed on a local machine or any other environment where the user intends to use as a base, to launch workflow runs and check statuses and logs. This can be done using either ``pip install -r requirement.txt`` or ``python setup.py install`` (see below **Installing_Tibanna_package_**)

2. One needs to deploy Tibanna on the AWS cloud, through the ``invoke deploy_unicorn`` command (see below **Deploying_Tibanna_to_AWS_**). This command deploys the set of AWS Lambda functions and a step function that coordinates the Lambda functions, in addition to configuring permissions for the AWS Lambda, EC2 instance and S3 buckets. These Lambda functions work as minions that launches and monitors individual executions. They live on the cloud and they are called only when an execution is submitted. Thanks to these Lambda functions, Tibanna does not require a constantly running master server to operate.

One may deploy as many copies of Tibanna as one wishes for different projects, with different bucket permissions and users. Unlike clusters, a copy of Tibanna is not limited to a single instance type or a shared runtime storage space (EBS). Tibanna's organization is more intuitive and practically more useful, since a single project may involve different input sizes and therefore different compute resource requirements. For developers, different copies of Tibanna may be used to test different modifications of Tibanna during development.

.. _Installing_Tibanna_package: https://tibanna.readthedocs.io/en/latest/installation.html#installing-tibanna-package
.. _Deploying_Tibanna_to_AWS: https://tibanna.readthedocs.io/en/latest/installation.html#deploying-tibanna-to-aws


Installing Tibanna package
--------------------------

Tibanna works with the following Python and pip versions.

- Python 2.7
- Pip 9, 10 or 18


Install Tibanna on your local machine or server from which you want to send commands to run workflows.

::

    # create a virtual environment with pip 9.0.3 (or 10 or 18)
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

To deploy Tibanna the AWS Cloud, one must first has an AWS account and an admin user credentials. If you do not have it yet, check out (**Before_using_Tibanna_**) first.


.. _Before_using_Tibanna: https://tibanna.readthedocs.io/en/latest/startaws.html


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

