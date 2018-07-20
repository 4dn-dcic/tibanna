=====================
# Tibanna
=====================

Tibanna is a metadata-aware workflow engine that deploys and monitors CWL/Docker-based pipelines to the AWS cloud. Tibanna is a main workflow management system used by the 4DN DCIC (4D Nucleome Data Coordination and Integration Center).

| [![Build Status](https://travis-ci.org/4dn-dcic/tibanna.svg?branch=master)](https://travis-ci.org/4dn-dcic/tibanna) | [![Code Quality](https://api.codacy.com/project/badge/Grade/d2946b5bc0704e5c9a4893426a7e0314)](https://www.codacy.com/app/4dn/tibanna?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=4dn-dcic/tibanna&amp;utm_campaign=Badge_Grade) | [![Test Coverage](https://api.codacy.com/project/badge/Coverage/d2946b5bc0704e5c9a4893426a7e0314)](https://www.codacy.com/app/4dn/tibanna?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=4dn-dcic/tibanna&amp;utm_campaign=Badge_Coverage) |

***

## Table of contents
* [Overview](#overview)
* [Installation](#installation)
  * [Dependency](#dependency)
  * [Admin](#admin)
  * [User](#user)
* [Commands](#commands)
  * [Deploying Tibanna](#deploying-tibanna)
  * [Execution of workflows using Tibanna](#execution-of-workflows-using-tibanna)
* [CWL versions](#cwl-versions)
* [4DN-DCIC-ONLY](#4dn-dcic-only)
  * [Webdev testing for Pony](#Webdev-testing-for-pony)
  * [Example Input Json for Pony](#example-input-json-for-pony)
* [Directory Structure](#directory-structure)


***
## Overview
<img src="images/tibanna_diagram_20180207.png" width=500>

Tibanna is auto-triggered upon data submission to execute a relevant workflow on the data. It utilizes two-layer scheduling; an upstream regulator based on a state machine called AWS Step Function and a downstream workflow engine that runs Docker/CWL-based pipelines. Tibanna’s AWS Step Function launches several AWS Serverless Lambda functions that control workflow-related metadata generation/tracking and deployment of a workflow on a pre-custom-configured autonomous virtual machine (EC2 instance) (AWSEM; Autonomous Workflow Step Executor Machine).

In addition, Tibanna offers multi-layer real-time monitoring to ensure the workflows are executed flawlessly. AWSEM sends real time logs from Docker/CWL to a designated S3 Bucket; individual AWS Lambda functions are checked through AWS CloudWatch; AWS Step function communicates with users at the top level. The system allows users to ssh into the EC2 instance where a workflow is currently being executed, to allow detailed investigation. Tibanna uses AWS IAM roles to ensure secure access. We have also implemented an accompanying resource optimizer for Tibanna (https://github.com/4dn-dcic/pipelines-cwl/tree/master/Benchmark), which calculates total CPU, memory and space required for a specific workflow run to determine EC2 instance type and EBS (Elastic Block Store) volume size. The calculation is based on input size, workflow parameters and the benchmarking results characteristic of individual workflows. The resource optimizer is essential for automated parameterization of data-dependent workflow runs, while maximizing the benefit of the elasticity of the cloud platform. Tibanna currently uses this optimizer to auto-determine instance types and EBS sizes for 4DN workflow runs.

Tibanna has been evolving: originally developed for Desktop workflow submitter that launches an autonomous VM, then upgraded to a Chalice/Lambda/API-Gateway-based system that works with the Seven Bridges Genomics (SBG) platform, and it currently consists of the original modules integrated with AWS Step functions for upstream scheduling and monitoring, without SBG.

## Installation
### Dependency
* Python 2.7
* Pip 9.0.3 / 10.0.1
* The other dependencies are listed in `requirements.txt` and are auto-installed in the following steps.
* If you are 4DN-DCIC user, use the dependencies specified in `requirements-4dn.txt`. These include all the base requirements in `requirements.txt`, as well as other 4DN-specific pakages.

### Admin
As admin, you need to first set up Tibanna environment on your AWS account and create a usergroup with a shared permission to the environment.
```
# install tibanna package
virtualenv -p python2.7 ~/venv/tibanna
source ~/venv/tibanna/bin/activate

# install pip 9.0.3 (or 10.0.1)
python -m pip install pip==9.0.3  # or curl https://bootstrap.pypa.io/get-pip.py | python - 'pip==9.0.3'

git clone https://github.com/4dn-dcic/tibanna
cd tibanna
pip install -r requirements.txt  # if you're 4dn-dcic, use requirements-4dn.txt instead
```

Set up `awscli`: for more details see https://github.com/4dn-dcic/tibanna/blob/master/tutorials/tibanna_unicorn.md#set-up-aws-cli

To set up and deploy Tibanna, you need the following environmental variables set and *exported* on your local machine from which you're setting up/deploying Tibanna.
```
TIBANNA_AWS_REGION  # aws region (e.g. us-east-1)
AWS_ACCOUNT_NUMBER  # aws account number
```

If you're using a forked repo or want to use a specific branch set the following variables accordingly and export them. If you're using default (4dn-dcic/tibanna, master), no need to set these variables.
```
export TIBANNA_REPO_NAME=4dn-dcic/tibanna
export TIBANNA_REPO_BRANCH=master
```

Then, set up user group and permission on AWS by using `invoke setup_tibanna_env`.
```
invoke setup_tibanna_env --buckets=<bucket1>,<bucket2>,...   # add all the buckets your input/output files and log files will go to. The buckets must already exist.
```
As an example,
```
invoke setup_tibanna_env --buckets=my-tibanna-test-bucket,my-tibanna-test-input-bucket (the public has permission to these buckets - the objects will expire in 1 day and others may have access to the same bucket and read/overwrite/delete your objects. Use it only for testing Tibanna.)
```
If you're 4DN-DCIC, you could do the following.
```
invoke setup_tibanna_env --buckets=elasticbeanstalk-fourfront-webdev-files,elasticbeanstalk-fourfront-webdev-wfoutput,tibanna-output,4dn-aws-pipeline-run-json  # this is for 4dn-dcic. (the public does not have permission to these buckets)
```
The `setup_tibanna_env` command will create a usergroup that shares the permission to use a single tibanna environment. Multiple users can be added to this usergroup and multiple tibanna instances (step functions / lambdas) can be deployed. The usergroup created will be printed out on the screen after the command. (e.g. as below).
```
Tibanna usergroup default_6206 has been created on AWS.
```

Then, deploy tibanna (unicorn) to your aws account for a specific user group (for more details about tibanna deployment, see below)
* Note: you can only use unicorn (the core with no communication with 4DN portal). Pony is reserved for 4DN-DCIC.
```
invoke deploy_tibanna --usergroup=<usergroup> --sfn-type=unicorn
```
As an exmple,
```
invoke deploy_tibanna --usergroup=default_6206 --sfn-type=unicorn
```

To run a workflow on the tibanna (unicorn) deployed for the usergroup (for more details about running workflows, see below),
```
invoke run_workflow --workflow=tibanna_unicorn_<usergroup> --input-json=<input_json_for_a_workflow_run>
```
As an example you can try to run a test workflow as below.
```
invoke run_workflow --workflow=tibanna_unicorn_default_6206 --input-json=test_json/my_test_tibanna_bucket.json
```
Then, add users to the usergroup.


### User
As a user, you need to set up your awscli. You can only use `run_workflow` and you don't have permission to setup or deploy tibanna.
```
virtualenv -p python2.7 ~/venv/tibanna
source ~/venv/tibanna/bin/activate

# pip 9.0.3 or 10.0.1
python -m pip install pip==9.0.3  # or curl https://bootstrap.pypa.io/get-pip.py | python - 'pip==9.0.3'
git clone https://github.com/4dn-dcic/tibanna
cd tibanna
pip install -r requirements.txt
```

Set up `awscli`: for more details see https://github.com/4dn-dcic/tibanna/blob/master/tutorials/tibanna_unicorn.md#set-up-aws-cli

To run workflow on the tibanna (unicorn) deployed for the usergroup (for more details about running workflows, see below)
```
invoke run_workflow --workflow=tibanna_unicorn_<usergroup> --input-json=<input_json_for_a_workflow_run>
```
As an example,
```
invoke run_workflow --workflow=tibanna_unicorn_default_6206 --input-json=test_json/my_test_tibanna_bucket.json
```
* For more details, see[Tutorials/tibanna_unicorn.md](tutorials/tibanna_unicorn.md)


## Commands
### Deploying Tibanna
* To deploy Tibanna, you need the following environmental variables set on your local machine from which you're deploying Tibanna.
```
TIBANNA_AWS_REGION  # aws region (e.g. us-east-1)
AWS_ACCOUNT_NUMBER  # aws account number
```
If you're 4DN-DCIC and using Tibanna Pony, you need the additional environmental variables
```
SECRET  # aws secret key
```

To create a copy of tibanna (step function + lambdas)
```
invoke deploy_tibanna [--suffix=<suffixname>] [--sfn_type=<sfn_type>] [--tests]
# (use suffix for development version)
# example <suffixname> : dev
# <sfn_type> (step function type) is either 'pony' or 'unicorn' (default pony)
```
* example
```
invoke deploy_tibanna --suffix=dev2
```
The above command will create a step function named `tibanna_pony_dev2` that uses a set of lambdas with suffix `_dev2`, and deploys these lambdas.

* example 2
```
invoke deploy_tibanna --suffix=dev --sfn_type=unicorn
```
This example creates a step function named `tibanna_unicorn_dev` that uses a set of lambdas with suffix `_dev`, and deploys these lambdas. Using the `--tests` argument will ensure tests pass befor deploying; currently this is **NOT** available for users outside of 4DN-DCIC.

To deploy lambda functions (use suffix for development version lambdas)
```
# individual lambda functions
invoke deploy_core <lambda_name> [--suffix=<suffixname>]
# example <lambda_name> : run_task_awsem
# example <suffixname> : dev

# all lambda functions
invoke deploy_core all [--suffix=<suffixname>]
# example <suffixname> : dev
```

### Execution of workflows using Tibanna
To run workflow
```
invoke run_workflow --input-json=<input_json_file> [--workflow=<stepfunctionname>]
# <stepfunctionname> may be one of tibanna_pony, tibanna_unicorn or any tibanna step function name that was created by the create_workflow command.
```
For more detail, see https://github.com/4dn-dcic/tibanna/blob/master/tutorials/tibanna_unicorn.md#set-up-aws-cli

To rerun a failed job with the same input json
```
invoke rerun --exec-arn=<stepfunctionrun_arn> [--workflow=<stepfunctionname>]
# <stepfunctionname> may be one of tibanna_pony, tibanna_unicorn or tibanna_pony-dev
```
To rerun many jobs that failed after a certain time point
```
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
```

To kill all currently running jobs (killing only step functions not the EC2 instances)
```
invoke kill_all [--workflow=<stepfunctionname>]
```


## CWL versions
* draft3 uses AMI ami-cfb14bb5, script directory `awsf_cwl_draft3` or `awsf`, can be tested as below:
```
invoke run_workflow --workflow=tibanna_unicorn --input-json=test_json/awsem_bwa.runonly.json`
```
* v1.0 uses AMI ami-31caa14e, script directory `awsf_cwl_v1`, can be tested as below.
```
invoke run_workflow --workflow=tibanna_unicorn --input-json=test_json/awsem_bwa.runonly.v1.json`
```
* The AMI ID and script directory are specified inside the input json (`config`).


## 4DN-DCIC-ONLY
### Webdev testing for Pony
```
test_json/awsem_md5.json  
test_json/awsem_fastqc.json
test_json/awsem_bwa_new.json
test_json/awsem_pairsqc.json
test_json/awsem_hicpairs_easy.json
test_json/awsem_hic_processing_bam-2.pony.json
test_json/awsem_repliseq_parta-pony.json
```
* note: these files are listed in `webdevtestlist`. One could use this file for batch testing for a given tibanna pony instance like an example below for Mac (replace `tibanna_pony_uno` with your step function mame).
```
cat webdevtestlist | xargs -I{} sh -c "invoke run_workflow --workflow=tibanna_pony_uno --input-json={}"
```

### Example Input Json for Pony
```
{
    "app_name": "bwa-mem",
    "output_bucket": "elasticbeanstalk-fourfront-webdev-wfoutput",
    "workflow_uuid": "0fbe4db8-0b5f-448e-8b58-3f8c84baabf5",
    "parameters" :  {"nThreads": 4},
    "input_files" : [
       {
           "object_key": "4DNFIZQZ39L9.bwaIndex.tgz",
           "workflow_argument_name": "bwa_index",
           "uuid": "1f53df95-4cf3-41cc-971d-81bb16c486dd",
           "bucket_name": "elasticbeanstalk-fourfront-webdev-files"
       },
       {
           "workflow_argument_name": "fastq1",
           "bucket_name": "elasticbeanstalk-fourfront-webdev-files",
           "uuid": "1150b428-272b-4a0c-b3e6-4b405c148f7c",
           "object_key": "4DNFIVOZN511.fastq.gz"
       },
       {
           "workflow_argument_name": "fastq2",
           "bucket_name": "elasticbeanstalk-fourfront-webdev-files",
           "uuid": "f4864029-a8ad-4bb8-93e7-5108f462ccaa",
           "object_key": "4DNFIRSRJH45.fastq.gz"
       }
  ],
  "config": {
    "ebs_size": 30,
    "ebs_type": "io1",
    "json_bucket": "4dn-aws-pipeline-run-json",
    "ebs_iops": 500,
    "shutdown_min": 30,
    "copy_to_s3": true,
    "launch_instance": true,
    "password": "dragonfly",
    "log_bucket": "tibanna-output",
    "key_name": ""
  },
  "custom_pf_fields": {
    "out_bam": {
        "genome_assembly": "GRCh38"
    }
  }
}
```
* The 'app_name' field contains the name of the workflow.
* The 'output_bucket' field specifies the bucket where all the output files go to.
* The 'workflow_uuid' field contains the uuid of the 4DN workflow metadata.
* The 'parameters' field contains a set of workflow-specific parameters in a dictionary.
* The 'input_files' field specifies the argument names (matching the names in CWL), the input file metadata uuid and its bucket and object key name.
* The 'config' field is directly passed on to the second step, where instance_type, ebs_size, EBS_optimized are auto-filled, if not given.
* The 'custom_pf_fields' field contains a dictionary that can be directly passed to the processed file metadata. The key may be either 'ALL' (applies to all processed files) or the argument name for a specific processed file (or both).


## Directory Structure

## core
This is core functionality (a set of lambda functions) that relies on AWS STEP Function to manage the process of running pipelines.  Does stuff like stage files to correct place, run workflow, poll for results, put output files in s3 and update associated metadata on the fourfront system.

## awsf, awsf_cwl_draft3, awsf_cwl_v1
A set of tools for running docker- and cwl-based pipelines on AWS (AWSEM, Autonomous Workflow Step Executor Machine)
* [README](awsf/README.md) for more details - (this readme is currently outdated)

## old/lambda_sbg (deprecated)
A lambda function integrated with APIGateway, for managing pipelines on AWS and SBG
* [README](old/lambda_sbg/README.md) for more details
