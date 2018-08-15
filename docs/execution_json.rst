=====================
Input JSON Schema
=====================

The input json defines an individual execution. It has two parts, `args` and `config`. `args` contains information about pipeline, input files, output bucket, input parameters, etc. `config` has parameters about AWS such as instance type, EBS size, ssh password, etc.


args
----
:app_name:
    - <name of the app> (e.g. 'pairsam-parse-sort')
    - A alphanumeric string that can identify the pipeline/app. May contain '-' or '_'.

:app_version:
    - <version of the app> (e.g. 0.2.0)
    - Version of the pipeline/app, for the user to keep in track.

:cwl_directory_url:
    - <url_that_contains_cwl_file(s)>
    - (e.g. 'https://raw.githubusercontent.com/4dn-dcic/pipelines-cwl/0.2.0/cwl_awsem')
    - The url must be public.

:cwl_main_filename:
    - <main_cwl_file> (e.g. 'pairsam-parse-sort.cwl')
    - This file must be in the cwl url given by ``cwl_directory_url``.
    - The actual cwl link would be ``cwl_directory_url`` + '\' + ``cwl_main_file_name``

:cwl_child_filenames:
    - <list_of_cwl_files> or ``[]`` (e.g. ['step1.cwl', 'step2.cwl'])
    - An array of all the other cwl files that are called by the main cwl file. If the main CWL file is of 'workflow' type, the other CWL files corresponding to steps or subworkflows should be listed here.

:cwl_version:
    - either ``v1`` or ``draft-3``

:input_files:
    - A dictionary that contains input files. The keys must match the input argument names of the CWL.
    - It contains `bucket_name`, `object_key` and optionally `profile` if the bucket can only be accessed through profile (profile can be set during Tibanna deployment)
    - (e.g.

    ::

        {
            'bam': {
                'bucket_name': 'some_public_bucket',
                'object_key': 'some_directory/some_file_name.bam',
                'profile': 'user1'
            },
            'chromsize': {
                'bucket_name': 'suwangs_bucket',
                'object_key': 'some_other_directory/hg38.chrom.sizes'
            }
        }

    )

:secondary_files:
    - A dictionary of the same format as `input_file` but contains secondary files. The keys must match the input argument name of the CWL where the secondary file belongs.
    - (e.g.

    ::

        {
            'bam': {
                'bucket_name': 'some_public_bucket',
                'object_key': 'some_directory/some_file_name.bai',
                'profile': 'user1'
            }
        }

    )


:input_parameters:
    - A dictionary that contains input parameter values. Default parameters don't need to be included. The keys must match the input argument name of the CWL.
    - (e.g.

    ::

        {
            'nThreads': 16
        }

    )

:output_S3_bucket:
    - The name of the bucket where output files will be sent to.

:output_target:
    - A dictionary that contains a desired object keys to be put inside output bucket. This can be useful if, for example, the pipeline always generates an output file of the same name (e.g. report, output.txt, etc) but the user wants to distinguish them by sample names in the output bucket. If not set, the original output file names will be used as object key.
    - (e.g.

    ::

        {
          'out_pairsam': '7b932aca-62f6-4d42-841b-0d7496567103/4DNFIPJMZ922.sam.pairs.gz'
        }

    )

:secondary_output_target:
    - Similar to `output_target` but for secondary files.
    - (e.g.

    ::

        {
          'out_pairsam': '7b932aca-62f6-4d42-841b-0d7496567103/4DNFIPJMZ922.sam.pairs.gz.px2'
        }

    )



config
------

:ebs_size:
    - <ebs_size_in_gb>
    - It can be specified by the user or left to be 0 (auto-determine) if Benchmark function is available for a given workflow/pipeline.

:log_bucket:
    - <log_bucket_name>
    - This is where the logs of the Tibanna runs are sent to.

:json_bucket:
    - <log_bucket_name>
    - This is where Tibanna sends an instruction to for an AWSEM EC2 instance.

:instance_type:
    - <instance_type>
    - Instance type (e.g. t2.micro) can be specified by the user or left to be '' (auto-determine) if Benchmark function is available for a given workflow.

:EBS_optimized:
    - <ebs_optimized> ``true``, ``false`` or '' (blank)
    - Whether the specific instance type should be EBS_optimized. It can be True only for an instance type that can be EBS optimized. If instance type is unspecified, leave this as blank.

:shutdown_min:
    - either number of minutes or string 'now'
    - 'now' would make the EC2 instance to terminate immediately after a workflow run. This option saves cost if the pipeline is stable. If debugging may be needed, one could set shutdown_min to be for example, 30, in which case the instance will keep running for 30 minutes after completion of the workflow run. During this time, a user could ssh into the instance.

:password:
    - <password_for_ssh> or '' (blank)
    - One can use either password or key_name (below) as ssh mechanism, if the user wants an option to ssh into the instance manually for monitoring/debugging purpose. Tibanna itself does not use ssh.
    - The password can be any string and anyone with the password and the ip address of the EC2 instance can ssh into the machine.

:key_name:
    - <key_pair_name> or '' (blank)
    - One can use either password (above) or key_name as ssh mechanism, if the user wants an option to ssh into the instance manually for monitoring/debugging purpose. Tibanna itself does not use ssh.
    - The key pair should be an existing key pair and anyone with the key pair ``.pem`` file and the ip address of the EC2 instance can ssh into the machine.

:ebs_iops: 500
:ebs_type: io1



Example input json
------------------

::

    {
      "args": {
        "app_name": "pairsam-parse-sort",
        "app_version": "0.2.0"
        "cwl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/pipelines-cwl/0.2.0/cwl_awsem/",
        "cwl_main_filename": "pairsam-parse-sort.cwl",
        "cwl_child_filenames": [],
        "cwl_version": "draft-3",
        "input_files": {
          "bam": {
            "bucket_name": "some_public_bucket",
            "object_key": "5ae5edb2-8917-445a-b93f-46936a1478a8/4DNFI3F894Y3.bam",
            "profile": "user1"
          },
          "chromsize": {
            "bucket_name": "suwang",
            "object_key": "4a6d10ee-2edb-4402-a98f-0edb1d58f5e9/4DNFI823LSII.chrom.sizes"
          }
        },
        "secondary_files": {},
        "input_parameters": {
          "nThreads": 16
        },
        "output_S3_bucket": "suwang",
        "output_target": {
          "out_pairsam": "7b932aca-62f6-4d42-841b-0d7496567103/4DNFIPJMZ922.sam.pairs.gz"
        },
        "secondary_output_target": {}
      },
      "config": {
        "ebs_size": 0,
        "json_bucket": "suwang",
        "EBS_optimized": "",
        "ebs_iops": 500,
        "shutdown_min": 30,
        "instance_type": "",
        "ebs_type": "io1",
        "password": "whateverpasswordworks",
        "log_bucket": "suwang",
        "key_name": ""
      }
    }



