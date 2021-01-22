============
Installation
============

Tibanna's installation is two-step - installation of the tibanna package on the local machine and deployment of its serverless components to the AWS Cloud. Since the second step is separated from the first step, one may deploy as many copies of Tibanna as one wishes for different projects, with different bucket permissions and users.


Installing Tibanna package
--------------------------

Tibanna works with the following Python and pip versions.

- Python 3.6
- Pip 9, 10, 18, 19, 20


Install Tibanna on your local machine or server from which you want to send commands to run workflows.

First, create a virtual environment.

::

    # create a virtual environment
    virtualenv -p python3.6 ~/venv/tibanna
    source ~/venv/tibanna/bin/activate
  

Then, install Tibanna.
  
::

    pip install tibanna


Alternatively, use ``git clone`` followed by ``setup.py``

::

   # Alternatively installing tibanna package from github repo
    git clone https://github.com/4dn-dcic/tibanna
    cd tibanna
    python setup.py install


Starting version ``1.0.0``, there is also a Docker image that contains the same version of tibanna as the image tag. This image is used on the EC2 AWSEM instances and not for a local use. The image contains many other things including Docker, Singularity, Cromwell, cwltool, etc. in addition to Tibanna and therefore not recommended, but in case the above two somehow didn't work in your environment, and if you have Docker, you could try:

::

    docker run -it 4dndcic/tibanna-awsf:1.0.0 bash
    # You could use a different version tag instead of 1.0.0
    # you can also mount your local directories and files as needed.
 

AWS configuration
-----------------

To deploy and use Tibanna on the AWS Cloud, you must first have an AWS account.

Deployment requires an admin user credentials. For more details, check out https://aws.amazon.com/.

To only run workflows using Tibanna, you need a regular user credentials.

Once you have the user credentials, we can add that information to the local machine using one of the following three methods:

  1) using ``awscli`` 
  2) by manually creating two files in ``~/.aws``. 
  3) setting AWS environment variables

Details of each method is described below. Tibanna uses this information to know that you have the permission to deploy to your AWS account.


1) using ``awscli``


::

    # first install awscli - see below if this fails
    pip install awscli

    # configure AWS credentials and config through awscli
    aws configure


Type in your keys, region and output format ('json') as below.

::

    AWS Access Key ID [None]: <your_aws_key>
    AWS Secret Access Key [None]: <your_aws_secret_key>
    Default region name [None]: us-east-1
    Default output format [None]: json


2) by manually creating two files in ``~/.aws``


Alternatively, (in case you can't install ``awscli`` for any reason (e.g. ``PyYAML`` version conflict)), do the following manually to set up AWS credentials and config.

::

    mkdir ~/.aws


Add the following to ``~/.aws/credentials``.

::

    [default]
    aws_access_key_id = <your_aws_key>
    aws_secret_access_key = <your_aws_secret_key>


Add the following to ``~/.aws/config``.

::

    [default]
    region = us-east-1
    output = json


3) setting AWS environment variables


Alternatively, you can directly set AWS credentials and config as environment variables
(instead of creating ``~/.aws/credentials`` and ``~/.aws/config``).

::

    export AWS_ACCESS_KEY_ID=<AWS_ACCESS_KEY>
    export AWS_SECRET_ACCESS_KEY=<AWS_SECRET_ACCESS_KEY>
    export AWS_DEFAULT_REGION=<AWS_DEFAULT_REGION>



Tibanna environment variables
-----------------------------

Note: starting ``0.9.0``, users do not need to export ``AWS_ACCOUNT_NUMBER`` and ``TIBANNA_AWS_REGION`` any more.


Deploying Tibanna Unicorn to AWS
--------------------------------

*Note: You have to have admin permission to deploy unicorn to AWS and add user to a tibanna permission group*

If you're using a forked Tibanna repo or want to use a specific branch, set the following variables as well before deployment. They will be used by the EC2 (VM) instances to grab the right scripts from the `awsf` directory of the right tibanna repo/branch. If you're using default (``4dn-dcic/tibanna``, ``master``), no need to set these variables.

::

    # only if you're using a forked repo
    export TIBANNA_REPO_NAME=<git_hub_repo_name>  # (default: 4dn-dcic/tibanna)
    export TIBANNA_REPO_BRANCH=<git_hub_branch_name>  # (default: master)


If you're using an external bucket with a separate credential, you can give the permission to this bucket to tibanna unicorn during deployment by setting the following additional environment variables before deploying. This credential will be added as profile ``user1`` on the EC2 instances to run. This profile name can be added to input file specifications for the files that require this external credential. For most cases, this part can be ignored.

::

    # only if you're using an external bucket with a separate credential
    export TIBANNA_PROFILE_ACCESS_KEY=<external_profile_access_key>
    export TIBANNA_PROFILE_SECRET_KEY=<external_profile_secret_key>


Then, deploy a copy of Tibanna as below.

If you want to operate multiple copies of Tibanna (e.g. for different projects), you can try to name each copy of Tibanna using ``--usergroup`` option (by default the name is ``default_<random_number>``).

Here, we're naming it ``hahaha`` - come up with a better name if you want to.


::

    tibanna deploy_unicorn --usergroup=hahaha
    # This will give permission to only public tibanna test buckets.
    # To add permission to other private or public buckets, use --buckets option.


Run a test workflow
-------------------

The above command will first create a usergroup that shares the permission to use a single tibanna environment. Then, it will deploy a tibanna instance (step function / lambda). The name of the tibanna step function is added to your ``~/.bashrc`` file. Check that you can see the following line in the ``~/.bashrc`` file.

::

    # check your ~/.bashrc file
    tail -1 ~/.bashrc

You should be able to see the following.

::

    export TIBANNA_DEFAULT_STEP_FUNCTION_NAME=tibanna_unicorn_hahaha


To set this environmental variable,

::

    source ~/.bashrc


You can run a workflow using Tibanna if you're an admin user or if you are a user that belongs to the user group. The following command launches a workflow run. See below for what to feed as input json, which contains information about what buckets to use, where to find the workflow CWL/WDL or what command to run inside a docker container, what the output file names should be, etc.

::

    tibanna run_workflow --input-json=<input_json_for_a_workflow_run>


As an example you can try to run a test workflow as below. This one uses only public buckets ``my-tibanna-test-bucket`` and ``my-tibanna-test-input-bucket``. The public has permission to these buckets - the objects will expire in 1 day and others may have access to the same bucket and read/overwrite/delete your objects. Please use it only for initial testing of Tibanna.


First, create the input json file ``my_test_tibanna_input.json`` as below.

::

    {
      "args": {
        "app_name": "md5",
        "app_version": "0.2.6",
        "cwl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/pipelines-cwl/0.2.6/cwl_awsem_v1/",
        "cwl_main_filename": "md5.cwl",
        "cwl_version": "v1",
        "input_files": {
          "input_file": {
            "bucket_name": "my-tibanna-test-input-bucket",
            "object_key": "somefastqfile.fastq.gz"
          }
        },
        "output_S3_bucket": "my-tibanna-test-bucket",
        "output_target": {
          "report": "my_outdir/report"
        }
      },
      "config": {
        "run_name": "md5-public-test",
        "log_bucket": "my-tibanna-test-bucket"
      }
    }


::

    tibanna run_workflow --input-json=my_test_tibanna_input.json


Deploying Tibanna Unicorn with private buckets
----------------------------------------------

*Note: You have to have admin permission to deploy unicorn to AWS and add user to a tibanna permission group*


Creating a bucket
+++++++++++++++++

You can skip this section if you want to use existing buckets for input/output/logs.

If you are an admin or have a permission to create a bucket, you can either use the AWS Web Console or use the following command using `awscli`. For example, a data (input/output) bucket and a tibanna log bucket may be created. You could also separate input and output buckets, or have multiple input buckets, etc. Bucket names are globally unique.

::

    aws s3api create-bucket --bucket <bucketname>


**Example**

::

    aws s3api create-bucket --bucket montys-data-bucket  # choose your own data bucket name
    aws s3api create-bucket --bucket montys-tibanna-log-bucket  # choose your own log bucket name



Upload your files to the data bucket by using the following

::

    aws s3 cp <filename> s3://<bucketname>/<filename>
    aws s3 cp --recursive <dirname> s3://<bucketname>/<dirname>


**Example**

::

    aws s3 cp somebamfile.bam s3://montys-data-bucket/somebamfile.bam
    aws s3 cp --recursive montys-input-data-folder s3://montys-data-bucket/montys-input-data-folder



Deploying Tibanna
+++++++++++++++++

Let's try setting up Tibanna that uses private buckets. As you deploy your tibanna, add your private bucket names.
Again, you can name this new copy of Tibanna by specifying a new user group (e.g. ``lalala``.)


::

    tibanna deploy_unicorn --buckets=<bucket1>,<bucket2>,... --usergroup=lalala


**Example**


::

    tibanna deploy_unicorn --buckets=montys-data-bucket,montys-tibanna-log-bucket \
                          --usergroup=lalala

    # no space between bucket names!


Export the environmental variable for Tibanna step function name.

::

    source ~/.bashrc


Create an input json using your buckets.

Then, run workflow.

::

    tibanna run_workflow --input-json=<input_json>


Now we have two different copies of deployed Tibanna. According to your `~/.bashrc`, the latest deployed copy is your default copy. However, if you want to run a workflow on a different copy of Tibanna, use ``--sfn`` option. For example, now your default copy is ``lalala`` (the latest one), but you want to run our workflow on ``hahaha``. Then, do the following.

::

    tibanna run_workflow --input-json=<input_json> --sfn=tibanna_unicorn_hahaha


User permission
---------------

To deploy Tibanna, one must be an admin for an AWS account.
To run a workflow, the user must be either an admin or in the IAM group ``tibanna_<usergroup>``. To add a user to a user group, you have to be an admin. To do this, use the ``tibanna`` command.

::
 
    tibanna users


You will see the list of users.

**Example**

::

    user	tibanna_usergroup
    soo
    monty	


This command will print out the list of users.

::

    tibanna add_users --user=<user> --group=<usergroup>


For example, if you have a user named ``monty`` and you want to give permission to this user to user Tibanna ``lalala``. This will give this user permission to run and monitor the workflow, access the buckets that Tibanna usergroup ``lalala``  was given access to through ``tibanna deploy_unicorn --buckets=<b1>,<b2>,...``

::

    tibanna add_users --user=monty --group=lalala


Check users again.

::

    tibanna users


::

    user	tibanna_usergroup
    soo
    monty	lalala

Now ``monty`` can use ``tibanna_unicorn_lalala`` and access buckets ``montys-data-bucket`` and ``montys-tibanna-log-bucket``


