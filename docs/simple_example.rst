=======================
Simple Example Pipeline
=======================

md5
---


Pipeline script
+++++++++++++++

Let's try a very simple pipeline that calculates md5sum of an input file. We write a script named ``run.sh`` that calculates two md5sum values for a gzipped input file, one for compressed and one for uncompressed content of the file. The script creates an output file named ``report`` that contains two md5sum values. If the file is not gzipped, it simply repeats a regular md5sum value twice.

The pipeline/script could look as below.

::

    #!/bin/bash
    
    file=$1
    
    if [[ $file =~ \.gz$ ]]
    then
      MD_OUT=($(md5sum $file))
      CONTENT_MD_OUT=($(gunzip -c $file | md5sum))
    else
      MD_OUT=($(md5sum $file))
      CONTENT_MD_OUT=$MD_OUT
    fi
    
    MD=${MD_OUT[0]}
    CONTENT_MD=${CONTENT_MD_OUT[0]}
    echo "$MD" >> report
    echo "$CONTENT_MD" >> report


Docker image
++++++++++++

We already have a public docker image for this (``duplexa/md5:v2``) that contains script ``run.sh``. You can find it on Docker Hub: https://hub.docker.com/r/duplexa/md5/. If you want to use this public image, you can skip the following.

To create your own, first you need to install docker on your (local) machine.


1. First, create a directory (e.g. named ``md5``)

2. Put the above ``run.sh`` script in this directory.

3. Then, inside this directory create a file named  ``Dockerfile`` with the following content.


::

    # start from ubuntu docker image
    FROM ubuntu:16.04
    
    # general updates & installing necessary Linux components
    RUN apt-get update -y && apt-get install -y unzip
    
    # copy the pipeline script into the image
    # (in this case, /usr/local/bin)
    WORKDIR /usr/local/bin
    COPY run.sh .
    RUN chmod +x run.sh
    
    # default command
    CMD ["run.sh"]

4. Then, build docker image. You can use the same image name (``duplexa/md5:v2``) for this step, but it is recommended to replace ``duplexa`` with your preferred Docker Hub account name, to be able to push the image to Docker Hub later.

::

    docker build -t duplexa/md5:v2 .


5. Check the image

::

    docker images


6. Push the image to Docker Hub. You need an account to Docker Hub.

::

    docker login
    docker push duplexa/md5:v2



CWL
+++

A CWL file could look as below. This CWL file can be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/md5/md5.cwl. 
To use your own docker image, replace ``duplexa/md5:v2`` with your docker image name.
To use your own CWL file, put this CWL file in a place where you can access through http, so that Tibanna can download this file to the cloud using ``wget`` command.

::

    ---
    cwlVersion: v1.0
    baseCommand:
      - run.sh
    inputs:
      - id: "#gzfile"
        type:
          - File
        inputBinding:
          position: 1
    outputs:
      - id: "#report"
        type:
        - File
        outputBinding:
          glob: report
    hints:
      - dockerPull: duplexa/md5:v2
        class: DockerRequirement
    class: CommandLineTool



The pipeline is ready!


Data
++++

For input data, let's use a file named ``somefastqfile.fastq.gz`` on a public bucket named ``my-tibanna-test-input-bucket``.

(You could also upload your own file to your own bucket and set up Tibanna to access that bucket.)


Input json
++++++++++


To run the pipeline on a specific input file using Tibanna, we need to create an *input json* file for each execution (or a dictionary object if you're using Tibanna as a python module).

This json file can be found in https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/md5/md5_test_input.json.

::

    {
      "args": {
        "app_name": "md5",
        "app_version": "v2",
        "cwl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/md5",
        "cwl_main_filename": "md5.cwl",
        "cwl_child_filenames": [],
        "cwl_version": "v1",
        "input_files": {
          "gzfile": {
            "bucket_name": "my-tibanna-test-input-bucket",
            "object_key": "somefastqfile.fastq.gz"
          }
        },
        "secondary_files": {},
        "input_parameters": {},
        "output_S3_bucket": "my-tibanna-test-bucket",
        "output_target": {
          "report": "some_sub_dirname/my_first_md5_report"
        },
        "secondary_output_target": {}
      },
      "config": {
        "ebs_size": 10,
        "json_bucket": "my-tibanna-test-bucket",
        "EBS_optimized": false,
        "ebs_iops": 500,
        "shutdown_min": 30,
        "instance_type": "t2.micro",
        "ebs_type": "io1",
        "password": "whateverpasswordworks",
        "log_bucket": "my-tibanna-test-bucket",
        "key_name": ""
      }
    }


This json file specifies input (argument name ``gzfile``, matching the name in CWL) as ``somefastqfile.fastq.gz`` on bucket ``my-tibanna-test-input-bucket``. The output file will be renamed to ``some_sub_dirname/my_first_md5_report`` in a bucket named ``my-tibanna-test-bucket``. In the input json, we specify the CWL file (the ``cwl_main_filename`` field) and its url (the ``cwl_directory_url`` field, note that the file name itself is excluded from the url).

We also specified in ``config``, that we need 10GB space total (``ebs_size``) and we're going to run an EC2 instance (VM) of type ``t2.micro`` which comes with 1 CPU and 1GB memory.



Tibanna run
+++++++++++

To run Tibanna,

1. Sign up for AWS
2. Install and configure ``awscli``

  see Before_using_Tibanna_

3. Install Tibanna on your local machine

  see Installation_

4. Deploy Tibanna (link it to the AWS account)

  see Installation_


.. _Before_using_Tibanna: https://tibanna.readthedocs.io/en/latest/startaws.html
.. _Installation: https://tibanna.readthedocs.io/en/latest/installation.html


5. Run workflow as below.

::

    cd tibanna
    invoke run_workflow --input-json=examples/md5/md5_test_input.json


6. Check status

::

    invoke stat


