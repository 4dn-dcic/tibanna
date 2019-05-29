cond_merge
-----

This pipeline is an example of a conditional output.
It chooses between two tasks, ``paste`` and ``cat``, depending on the length of the input array (i.e. the number of input files). The former pastes input files horrizontally and the latter concatenates input files vertically. Since we're using generic commands, we do not need to create a pipeline software component or a Docker image. We will use the existing ``ubuntu:16.04`` Docker image. So, we will just do the following three steps.

1. create the pipeline description using *WDL*. (*CWL* does not support conditional statements)
2. prepare for a job definition that specifies pipeline, input files, parameters, resources, output target, etc.
3. run Tibanna.
 

Data
++++

For input data, let's use files named ``smallfile1``, ``smallfile2``, ``smallfile3`` and ``smallfile4`` in a public bucket named ``my-tibanna-test-input-bucket``. Each of these files contains a letter ('``a``', '``b``', '``c``', and '``d``', respectively). We feed an array of these files in the following formats (one with length 4, another with length 2):

  ::

      [smallfile1, smallfile2, smallfile3, smallfile4]

  ::

      [smallfile1, smallfile2]


(You could also upload your own file to your own bucket and set up Tibanna to access that bucket.)


Pipeline description
++++++++++++++++++++


This pipeline takes an input file array. If the length of the array is larger than 2 (more than 2 files), it runs ``paste``. If it is smaller than or equal to 2, it runs ``cat``. The former creates a pasted file and the latter creates a concatenated file.

In the former case (``paste``), the output would look like this:

  ::

      a  b  c  d


In the latter case (``cat``), the output would look like:

  ::

      a
      b


WDL
###
    
    WDL describes this pipeline in one file and it can be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/cond_merge/cond_merge.wdl. 
    To use your own WDL file, you'll need to make sure it is accessible via HTTP so Tibanna can download it with ``wget``: If you're using github, you could use raw.githubusercontent.com like the link above.
    Content-wise, this WDL does exactly the same as the above CWL.
    
    ::
    
        workflow cond_merge {
            Array[File] smallfiles = []
            if(length(smallfiles)>2) {
                call paste {input: files = smallfiles}
            }
            if(length(smallfiles)<=2) {
                call cat {input: files = smallfiles}
            }
        }
        
        task paste {
            Array[File] files = []
            command {
                paste ${sep=" " files} > pasted
            }
            output {
                File pasted = "pasted"
            }
            runtime {
                docker: "ubuntu:16.04"
            }
        }
        
        task cat {
            Array[File] files = []
            command {
                cat ${sep=" " files} > concatenated
            }
            output {
                File concatenated = "concatenated"
            }
            runtime {
                docker: "ubuntu:16.04"
            }
        } 
            

The pipeline is ready!



Job description
+++++++++++++++

To run the pipeline on a specific input file using Tibanna, we need to create an *job description* file for each execution (or a dictionary object if you're using Tibanna as a python module).

    
Job description for WDL
#######################

    If the user does not know (or does not want to manually control) which of the two outputs should be sent to S3, one can specify a global name for this output and associate it with the alternative output names. For example, in this case, we could set up a global name to be ``cond_merge.cond_merged`` and associate with two alternative names ``cond_merge.paste.pasted`` and ``cond_merge.cat.concatenated``. This way, either of the two will be recognized as ``cond_merge.cond_merged`` and will be treated as if it was not a conditional output from the user's perspective.

    An example job description for WDL is shown below and it can also be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/cond_merge/cond_merge_wdl_input.json. Another example with two input files can be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/cond_merge/cond_merge_wdl_input2.json. Note the field ``alt_cond_output_argnames`` under ``args``.
    
    
    ::
    
        {
          "args": {
            "app_name": "cond_merge",
            "app_version": "",
            "language": "wdl",
            "wdl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/cond_merge",
            "wdl_main_filename": "cond_merge.wdl",
            "wdl_child_filenames": [],
            "input_files": {
              "cond_merge.smallfiles": {
                "bucket_name": "my-tibanna-test-input-bucket",
                "object_key": ["smallfile1", "smallfile2", "smallfile3", "smallfile4"]
              }
            },
            "secondary_files": {},
            "input_parameters": {},
            "output_S3_bucket": "my-tibanna-test-bucket",
            "output_target": {
                "cond_merge.cond_merged": "some_sub_dirname/my_first_cond_merged_file"
            },
            "alt_cond_output_argnames": {
                "cond_merge.cond_merged": ["cond_merge.paste.pasted", "cond_merge.cat.concatenated"]
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
        tibanna run_workflow --input-json=examples/cond_merge/cond_merge_wdl_input.json
        tibanna run_workflow --input-json=examples/cond_merge/cond_merge_wdl_input2.json
    

6. Check status

::

    tibanna stat


