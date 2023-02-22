md5
---

We will preprare a pipeline that calculated md5sum. To create this pipeline and run it through Tibanna, we will do the following.

1. prepare for a component of the pipeline as a script (it could be a binary program)
2. package the components as a Docker image
3. create the pipeline description using either *CWL* or *WDL*.
4. prepare for a job definition that specifies pipeline, input files, parameters, resources, output target, etc.
5. run Tibanna.
 

Data
++++

For input data, let's use a file named ``somefastqfile.fastq.gz`` on a public bucket named ``my-tibanna-test-input-bucket``.

(You could also upload your own file to your own bucket and set up Tibanna to access that bucket.)


Pipeline component
++++++++++++++++++

Let's try a very simple pipeline that calculates the md5sum of an input file. We'll write a script named ``run.sh`` that calculates two md5sum values for a gzipped input file, one for the compressed and one for the uncompressed content of the file. The script creates an output file named ``report`` that contains two md5sum values. If the file is not gzipped, it simply repeats a regular md5sum value twice.

The pipeline/script could look like this:

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

We already have a public docker image for this (``duplexa/md5:v2``) that contains script ``run.sh``. You can find it on Docker Hub: https://hub.docker.com/r/duplexa/md5/. If you want to use this public image, you can skip the following steps.

To create your own, first you need to install docker on your (local) machine.


1. First, create a directory (e.g. named ``md5``)

2. Put the above ``run.sh`` script in this directory.

3. Then, inside this directory create a file named  ``Dockerfile`` with the following content.


::

    # start from ubuntu docker image
    FROM ubuntu:20.04
    
    # general updates & installing necessary Linux components
    RUN apt-get update -y && apt-get install -y unzip
    
    # copy the pipeline script into the image
    # (in this case, /usr/local/bin)
    WORKDIR /usr/local/bin
    COPY run.sh .
    RUN chmod +x run.sh
    
    # default command
    CMD ["run.sh"]

4. Then, build the docker image. You can use the same image name (``duplexa/md5:v2``) for this step, but it is recommended to replace ``duplexa`` with your preferred Docker Hub account name, to be able to push the image to Docker Hub later.

::

    docker build -t my_account/md5:v2 .


5. Check the image

::

    docker images


6. Push the image to Docker Hub. You will need an account on Docker Hub.

::

    docker login
    docker push my_account/md5:v2



Pipeline description
++++++++++++++++++++

CWL
###
    
    A sample CWL file is below. This CWL file can be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/md5/md5.cwl. 
    To use your own docker image, replace ``duplexa/md5:v2`` with your docker image name.
    To use your own CWL file, you'll need to make sure it is accessible via HTTP so Tibanna can download it with ``wget``: If you're using github, you could use raw.githubusercontent.com like the link above.
    
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
    
    
WDL
###
    
    Like CWL, WDL describes a pipeline structure. We describe individual runs (jobs) as separate json files.
    
    A sample WDL file is below. This WDL file can be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/md5/md5.wdl. 
    To use your own docker image, replace ``duplexa/md5:v2`` with your docker image name.
    To use your own WDL file, you'll need to make sure it is accessible via HTTP so Tibanna can download it with ``wget``: If you're using github, you could use raw.githubusercontent.com like the link above.
    Content-wise, this WDL does exactly the same as the above CWL.
    
    ::
    
        workflow md5 {
            call md5_step
        }
        
        task md5_step {
            File gzfile
            command {
                run.sh ${gzfile}
            }
            output {
                File report = "report"
            }
            runtime {
                docker: "duplexa/md5:v2"
            }
        }
    
    
    The pipeline is ready!


Shell
#####

    A list of shell commands can also be used. It could be something like this.


    ::

        run.sh input.gz


    A shell command doesn't have to be written in a file. The command itself can be passed to Tibanna as part of the job description json.


Job description
+++++++++++++++

To run the pipeline on a specific input file using Tibanna, we need to create an *job description* file for each execution (or a dictionary object if you're using Tibanna as a python module).


Job description for CWL
#######################
    
    The example job description for CWL is shown below and it can also be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/md5/md5_cwl_input.json.
    
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
            "EBS_optimized": false,
            "instance_type": "t3.micro",
            "password": "whateverpasswordworks",
            "log_bucket": "my-tibanna-test-bucket"
          }
        }
    
    
    The json file specifies the input with ``gzfile``, matching the name in CWL. In this example it is ``somefastqfile.fastq.gz`` on bucket ``my-tibanna-test-input-bucket``. The output file will be renamed to ``some_sub_dirname/my_first_md5_report`` in a bucket named ``my-tibanna-test-bucket``. In the input json, we specify the CWL file with ``cwl_main_filename`` and its url with ``cwl_directory_url``. Note that the file name itself is not included in the url).
    
    We also specified in ``config``, that we need 10GB space total (``ebs_size``) and we're going to run an EC2 instance (VM) of type ``t3.micro`` which comes with 1 CPU and 1GB memory.
    
    
Job description for WDL
#######################
    
    The example job description for WDL is shown below and it can also be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/md5/md5_wdl_input.json.
    
    Content-wise, it is exactly the same as the one for CWL above. Notice that the only difference is that 1) you specify fields "wdl_main_filename", "wdl_child_filenames" and "wdl_directory_url" instead of "cwl_main_filename", "cwl_child_filenames", "cwl_directory_url", and "cwl_version" in ``args``, that 2) you have to specify ``"language" : "wdl"`` in ``args`` and that 3) when you refer to an input or an output, CWL allows you to use a global name (e.g. ``gzfile``, ``report``), whereas with WDL, you have to specify the workflow name and the step name (e.g. ``md5.md5_step.gzfile``, ``md5.md5_step.report``).
    
    ::
    
        {
          "args": {
            "app_name": "md5",
            "app_version": "v2",
            "wdl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/md5",
            "wdl_main_filename": "md5.wdl",
            "wdl_child_filenames": [],
            "language": "wdl",
            "input_files": {
              "md5.md5_step.gzfile": {
                "bucket_name": "my-tibanna-test-input-bucket",
                "object_key": "somefastqfile.fastq.gz"
              }
            },
            "secondary_files": {},
            "input_parameters": {},
            "output_S3_bucket": "my-tibanna-test-bucket",
            "output_target": {
              "md5.md5_step.report": "some_sub_dirname/my_first_md5_report"
            },
            "secondary_output_target": {}
          },
          "config": {
            "ebs_size": 10,
            "EBS_optimized": false,
            "instance_type": "t3.micro",
            "password": "whateverpasswordworks",
            "log_bucket": "my-tibanna-test-bucket"
          }
        }
    
    
    The json file specifies the input with ``md5.md5_step.gzfile``, matching the name in WDL. In this example it is ``somefastqfile.fastq.gz`` on bucket ``my-tibanna-test-input-bucket``. The output file will be renamed to ``some_sub_dirname/my_first_md5_report`` in a bucket named ``my-tibanna-test-bucket``. In the input json, we specify the WDL file with ``wdl_filename`` and its url with ``wdl_directory_url``. Note that the file name itself is not included in the url).
    
    The config field is identical to the CWL input json. In ``config``, we specify that we need 10GB space total (``ebs_size``) and we're going to run an EC2 instance (VM) of type ``t3.micro`` which comes with 1 CPU and 1GB memory.



Job description for shell
#########################

    The job description for running shell commands requires ``command`` and ``container_image`` fields. The former is a list of commands and the latter is the Docker image name.

    The current working directory for running shell commands is ``/data1/shell`` and it can be requested that input files be copied from S3 to this directory.

    In the following example, input file ``s3://my-tibanna-test-input-bucket/somefastqfile.fastq.gz`` is copied to ``/data1/shell`` as ``input.gz`` which matches the input file in the ``command`` field (``run.sh input.gz``). The output file ``report`` in the same directory is copied to the output bucket ``my-tibanna-test-bucket`` as ``some_sub_dirname/my_first_md5_report``.


    This json file can be found at https://github.com/4dn-dcic/tibanna/blob/master/examples/md5/md5_shell_input.json


    ::
    
        {
          "args": {
            "container_image": "duplexa/md5:v2",
            "command": ["run.sh input.gz"],
            "language": "shell",
            "input_files": {
              "file:///data1/shell/input.gz": "s3://my-tibanna-test-input-bucket/somefastqfile.fastq.gz"
            },
            "secondary_files": {},
            "input_parameters": {},
            "output_S3_bucket": "my-tibanna-test-bucket",
            "output_target": {
              "file:///data1/shell/report": "some_sub_dirname/my_first_md5_report"
            },
            "secondary_output_target": {}
          },
          "config": {
            "ebs_size": 10,
            "instance_type": "t3.micro",
            "EBS_optimized": false,
            "password": "whateverpasswordworks",
            "log_bucket": "my-tibanna-test-bucket"
          }
        }



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

    For CWL,
    
    ::
    
        cd tibanna
        tibanna run_workflow --input-json=examples/md5/md5_cwl_input.json
    
    or for WDL,
    
    ::
    
        cd tibanna
        tibanna run_workflow --input-json=examples/md5/md5_wdl_input.json


    or for shell,

    ::

        cd tibanna
        tibanna run_workflow --input-json=examples/md5/md5_shell_input.json    


6. Check status

::

    tibanna stat


