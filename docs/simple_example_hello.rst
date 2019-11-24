hello
-----

We will run a command that prints *hello world* through Tibanna. To do this, we just need to prepare for a job description json and run tibanna.


Job description
+++++++++++++++

To run the pipeline on a specific input file using Tibanna, we need to create an *job description* file for each execution (or a dictionary object if you're using Tibanna as a python module).

The job description for running shell commands requires ``command`` and ``container_image`` fields. The former is a list of commands and the latter is the Docker image name. Here, we use ``ubuntu:16.04`` image and use an ``echo`` command. Notice that double-quotes are escaped inside the command string. We're passing an environment variable ``$NAME`` through the field ``input_env``. Also notice that the environment variable's ``$`` sign is prefixed with an escaped backslash in the ``command`` string.

In the following example, the output file ``hello.txt`` in the same directory is copied to the output bucket ``my-tibanna-test-bucket`` as ``some_sub_dirname/my_first_hello.txt``.


    ::
    
        {       
          "args": {
            "container_image": "ubuntu:16.04",
            "command": ["echo \"Hello world, \\$NAME!\" > hello.txt"],
            "language": "shell",
            "input_files": {},
            "secondary_files": {},
            "input_parameters": {},
            "input_env": {"NAME": "Soo"},
            "output_S3_bucket": "my-tibanna-test-bucket",
            "output_target": {
              "file:///data1/shell/hello.txt": "some_sub_dirname/my_first_hello.txt"
            },      
            "secondary_output_target": {}
          },      
          "config": {
            "ebs_size": 10,
            "instance_type": "t2.micro",
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

    ::

        cd tibanna
        tibanna run_workflow --input-json=examples/hello/hello_shell_input.json    


6. Check status

::

    tibanna stat


