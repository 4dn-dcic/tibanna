merge
-----

This pipeline is an example of a nested input file array (e.g. ``[[f1, f2], [f3, f4]]``).
It consists of two steps, ``paste`` and ``cat``, the former pastes input files horrizontally and the latter concatenates input files vertically. Since we're using generic commands, we do not need to create a pipeline software component or a Docker image. We will use the existing ``ubuntu:16.04`` Docker image. So, we will just do the following three steps.

1. create the pipeline description using either *CWL* or *WDL*.
2. prepare for a job definition that specifies pipeline, input files, parameters, resources, output target, etc.
3. run Tibanna.
 

Data
++++

For input data, let's use files named ``smallfile1``, ``smallfile2``, ``smallfile3`` and ``smallfile4`` in a public bucket named ``my-tibanna-test-input-bucket``. Each of these files contains a letter ('``a``', '``b``', '``c``', and '``d``', respectively). We feed an array of array of these files in the following format:

  ::

      [[smallfile1, smallfile2], [smallfile3, smallfile4]]


(You could also upload your own file to your own bucket and set up Tibanna to access that bucket.)


Pipeline description
++++++++++++++++++++

Thie pipeline takes an input 'smallfiles' which is an array of array of files. The input is scattered to the first step ``paste``, which means that each element of 'smallfiles' (i.e. each array of files) goes as the input of ``paste``, and the outputs will be gathered into an array before it is passed to the next step. From the input data above, there will be two runs of ``paste`` and one will take in ``[smallfile1, smallfile2]`` and the other ``[smallfile3, smallfile4]``, and the outputs will be combined into an array *[<paste_output1>, <paste_output2>]*. The second step, ``cat`` takes in this array and concatenates them.

So, the output of the two ``paste`` runs would look like:

  ::

      a  b


  ::

      c  d


And the output of the ``cat`` (or the output of the workflow) would look like:

  ::

      a  b
      c  d


CWL
###

    Since this is a multi-step pipeline, we use three CWL files, ``merge.cwl`` (master workflow CWL) and two other CWL files ``paste.cwl`` and ``cat.cwl`` that are called by ``merge.cwl``.
    
    These CWL files can be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/merge/merge.cwl, https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/merge/paste.cwl and https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/merge/cat.cwl.
    To use your own CWL file, you'll need to make sure it is accessible via HTTP so Tibanna can download it with ``wget``: If you're using github, you could use raw.githubusercontent.com like the link above.
   
    The following is ``merge.cwl``. It is of class 'workflow' and defines inputs, outputs and steps. For the other two CWL files (``paste.cwl`` and ``cat.cwl``), see the links above.

    ::

        ---
        class: Workflow
        cwlVersion: v1.0
        inputs:
           smallfiles:
             type:
               type: array
               items:
                 type: array
                 items: File
        outputs:
          - 
            id: "#merged"
            type: File
            outputSource: "#cat/concatenated"
        steps:
          -
            id: "#paste"
            run: "paste.cwl"
            in:
            - 
              id: "#paste/files"
              source: "smallfiles"
            scatter: "#paste/files"
            out:
            -
              id: "#paste/pasted"
          -
            id: "#cat"
            run: "cat.cwl"
            in:
            - 
              id: "#cat/files"
              source: "#paste/pasted"
            out:
            -
              id: "#cat/concatenated"
        requirements:
          -
            class: "ScatterFeatureRequirement"   
   
 
    The pipeline is ready!
    
    
WDL
###
    
    WDL describes this pipeline in one file and it can be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/merge/merge.wdl. 
    To use your own WDL file, you'll need to make sure it is accessible via HTTP so Tibanna can download it with ``wget``: If you're using github, you could use raw.githubusercontent.com like the link above.
    Content-wise, this WDL does exactly the same as the above CWL.
    
    ::
    
        workflow merge {
            Array[Array[File]] smallfiles = []
            scatter(smallfiles_ in smallfiles) {
                call paste {input: files = smallfiles_}
            }
            call cat {input: files = paste.pasted}
            output {
                File merged = cat.concatenated
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


Job description for CWL
#######################
    
    The example job description for CWL is shown below and it can also be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/merge/merge_cwl_input.json.
    
    ::
    
        {
          "args": {
            "app_name": "merge",
            "app_version": "",
            "cwl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/merge",
            "cwl_main_filename": "merge.cwl",
            "cwl_child_filenames": ["paste.cwl", "cat.cwl"],
            "cwl_version": "v1",
            "input_files": {
              "smallfiles": {
                "bucket_name": "my-tibanna-test-input-bucket",
                "object_key": [["smallfile1", "smallfile2"], ["smallfile3", "smallfile4"]]
              }
            },
            "secondary_files": {},
            "input_parameters": {},
            "output_S3_bucket": "my-tibanna-test-bucket",
            "output_target": {
              "merged": "some_sub_dirname/my_first_merged_file"
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
    
    The json file specifies the input nested file array ("smallfiles") (``[["smallfile1", "smallfile2"], ["smallfile3", "smallfile4"]]``), matching the name in CWL. The output file will be renamed to ``some_sub_dirname/my_first_merged_file`` in a bucket named ``my-tibanna-test-bucket``. In the input json, we specify the CWL file with ``cwl_main_filename`` and its url with ``cwl_directory_url``. Note that the file name itself is not included in the url). Note that child CWL files are also specified in this case (``"cwl_child_filenames": ["paste.cwl", "cat.cwl"]``).
    
    We also specified in ``config``, that we need 10GB space total (``ebs_size``) and we're going to run an EC2 instance (VM) of type ``t2.micro`` which comes with 1 CPU and 1GB memory.
    
    
Job description for WDL
#######################
    
    The example job description for WDL is shown below and it can also be found at https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/merge/merge_wdl_input.json.
    
    Content-wise, it is exactly the same as the one for CWL above. Notice that the only difference is that 1) you specify fields "wdl_filename" and "wdl_directory_url" instead of "cwl_main_filename", "cwl_child_filenames", "cwl_directory_url", and "cwl_version" in ``args``, that 2) you have to specify ``"language" : "wdl"`` in ``args`` and that 3) when you refer to an input or an output, CWL allows you to use a global name (e.g. ``smallfiles``, ``merged``), whereas with WDL, you have to specify the workflow name (e.g. ``merge.smallfiles``, ``merge.merged``). We omit the step names in this case because we use global variables that are passed to and from the steps.
    
    ::
    
        {
          "args": {
            "app_name": "merge",
            "app_version": "",
            "language": "wdl",
            "wdl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/examples/merge",
            "wdl_filename": "merge.wdl",
            "input_files": {
              "merge.smallfiles": {
                "bucket_name": "my-tibanna-test-input-bucket",
                "object_key": [["smallfile1", "smallfile2"], ["smallfile3", "smallfile4"]]
              }
            },
            "secondary_files": {},
            "input_parameters": {},
            "output_S3_bucket": "my-tibanna-test-bucket",
            "output_target": {
              "merge.merged": "some_sub_dirname/my_first_merged_file"
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

    For CWL,
    
    ::
    
        cd tibanna
        invoke run_workflow --input-json=examples/merge/merge_cwl_input.json
    
    or for WDL,
    
    ::
    
        cd tibanna
        invoke run_workflow --input-json=examples/merge/merge_wdl_input.json
    

6. Check status

::

    invoke stat


