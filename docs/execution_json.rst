===========================
Job Description JSON Schema
===========================

The Job Description json (input of Tibanna) defines an individual execution. It has two parts, `args` and `config`. `args` contains information about pipeline, input files, output bucket, input parameters, etc. `config` has parameters about AWS such as instance type, EBS size, ssh password, etc.


Example job description for CWL
-------------------------------

::

    {
      "args": {
        "cwl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/pipelines-cwl/0.2.0/cwl_awsem/",
        "cwl_main_filename": "pairsam-parse-sort.cwl",
        "cwl_version": "v1",
        "input_files": {
          "bam": {
            "bucket_name": "montys-data-bucket",
            "object_key": "dataset1/sample1.bam"
          },
          "chromsize": {
            "bucket_name": "montys-data-bucket",
            "object_key": "references/hg38.chrom.sizes"
          }
        },
        "input_parameters": {
          "nThreads": 16
        },
        "input_env": {
          "TEST_ENV_VAR": "abcd"
        },
        "output_S3_bucket": "montys-data-bucket",
        "output_target": {
          "out_pairsam": "output/dataset1/sample1.sam.pairs.gz"
        },
        "secondary_output_target": {
          "out_pairsam": "output/dataset1/sample1.sam.pairs.gz.px2"
        }
      },
      "config": {
        "instance_type": "t3.micro",
        "ebs_size": 10,
        "EBS_optimized": true,
        "log_bucket": "montys-log-bucket"
      }
    }



args
----

The ``args`` field describe pipeline, input and output.


Pipeline specification
######################

CWL-specific
++++++++++++

:cwl_directory_url:
    - <url_that_contains_cwl_file(s)>
    - (e.g. 'https://raw.githubusercontent.com/4dn-dcic/pipelines-cwl/0.2.0/cwl_awsem')
    - (e.g. 's3://bucketname/dirname/dirname2')
    - The http url must be public.
    - For the s3 url, the bucket must have been included during the ``deploy_unicorn`` run (accessible by tibanna)

:cwl_directory_local:
    - <local_directory_that_contains_cwl_file(s)>
    - If this is set, ``cwl_directory_url`` can be skipped.

:cwl_main_filename:
    - <main_cwl_file> (e.g. 'pairsam-parse-sort.cwl')
    - This file must be in the cwl url given by ``cwl_directory_url``.
    - The actual cwl link would be ``cwl_directory_url`` + '\' + ``cwl_main_file_name``

:cwl_child_filenames:
    - <list_of_cwl_files> or ``[]`` (e.g. ['step1.cwl', 'step2.cwl'])
    - An array of all the other cwl files that are called by the main cwl file. If the main CWL file is of 'workflow' type, the other CWL files corresponding to steps or subworkflows should be listed here.

:cwl_version:
    - either ``v1`` or ``draft-3`` (starting with tibanna version ``1.0.0``, ``draft-3`` is no longer supported.)

:singularity:
    - This option uses Singularity to run Docker images internally (slower). This option does NOT support native Singularity images, since CWL does not support native Singularity images.
    - either ``true`` or ``false``
    - This is an optional field. (default ``false``)


WDL-specific
++++++++++++

:language:
    - This field must be set to ``wdl`` to run a WDL pipeline.
    - To run an old version (draft2) of WDL, set it to ``wdl_draft2``. This will direct Tibanna to specifically use an older version of Cromwell. Some draft2 WDLs may be supported by the later version of Cromwell. Use the ``wdl_draft2`` option only if the old WDL does not work with the later version of Cromwell.

:wdl_directory_url:
    - <url_that_contains_wdl_file(s)>
    - (e.g. 'https://raw.githubusercontent.com/4dn-dcic/pipelines-cwl/master/wdl')
    - (e.g. 's3://bucketname/dirname/dirname2')
    - The http url must be public.
    - For the s3 url, the bucket must have been included during the ``deploy_unicorn`` run (accessible by tibanna)

:wdl_directory_local:
    - <local_directory_that_contains_wdl_file(s)>
    - If this is set, ``wdl_directory_url`` can be skipped.

:wdl_main_filename:
    - <main_wdl_file> (e.g. 'pairsam-parse-sort.wdl')
    - This file must be in the wdl url given by ``wdl_directory_url``.
    - The actual wdl link would be ``wdl_directory_url`` + '\' + ``wdl_file_name``

:wdl_child_filenames:
    - <list_of_wdl_files> or ``[]`` (e.g. ['subworkflow1.wdl', 'subworkflow2.wdl'])
    - An array of all the other wdl files that are called by the main wdl file. This could happen if there are the main WDL file is using another WDL file as a subworkflow.


Shell command-specific
++++++++++++++++++++++

:language:
    - This field must be set to ``shell`` to run a shell command without CWL/WDL.

:container_image:
    - <Docker image name>

:command:
    - <shell command to be executed inside the Docker container>
    - a pair of nested double quotes are allowed
    - (e.g.

    ::

        "command": "echo \"haha\" > outfile"


Snakemake-specific
++++++++++++++++++

:language:
    - This field must be set to ``snakemake`` to run a Snakemake pipeline.

:container_image:
    - This is a required field.
    - It is highly recommended to use the official Snakemake Docker image
      (``snakemake/snakemake``)

:command:
    - This is a required field.
    - Most likely it will be ``snakemake`` but it can be run with other ``snakemake`` otions.
    - (e.g.

    ::

        "command": "snakemake <target> --use-conda"

    - a pair of nested double quotes are allowed
    - (e.g.

    ::

        "command": "snakemake <target> --config=region=\"22:30000000-40000000\"


:snakemake_main_filename:
    - This is a required field.
    - Most likely it will be ``Snakefile`` (do not include directory name).

:snakemake_child_filenames:
    - This is an optional field.
    - This may include other workflow-related files including ``env.yml``, ``config.json``, etc.
      (Do not include directory name).

:snakemake_directory_local:
    - The location (directory path) of the `snakemake_main_filename` and ``snake_child_filenames``.
    - Use this if the workflow files are local.

:snakemake_directory_url:
    - The url (directory only) of the `snakemake_main_filename` and ``snake_child_filenames``.
    - Use this if the worlfow files are accessible through a url (either ``http://`` or ``s3://``.


Other pipeline-related fields
+++++++++++++++++++++++++++++

:app_name:
    - <name of the app> (e.g. 'pairsam-parse-sort')
    - A alphanumeric string that can identify the pipeline/app. May contain '-' or '_'.
    - This field is optional and is used only by ``Benchmark`` which auto-termines instance type
      and EBS size based on input size and parameters. If the workflow doesn't have an associated
      Benchmark function, this field can be omitted, but ``instance_type`` (or ``mem`` and ``cpu``),
      ``ebs_size`` (unless using default 10GB), ``EBS_optimized`` (unless using default ``False``)
      must be specified in ``config``.

:app_version:
    - optional
    - <version of the app> (e.g. 0.2.0)
    - Version of the pipeline/app, for the user to keep in track.

:language:
    - 'cwl_v1', 'cwl_draft3' (tibanna < ``1.0.0`` only) or 'wdl' (='wdl_v1' for backward compatibility) or 'wdl_draft2' or 'wdl_v1' (tibanna >= ``1.0.0``)
    - For WDL, it is a required field. For CWL, the language field can be omitted.


Input data specification
########################

:input_files:
    - A dictionary that contains input files. The keys must match the input argument names of the CWL/WDL.
    - It contains ``bucket_name``, ``object_key`` as required fields.
    - Optionally, it may contain the following fields:

      - ``profile`` if the bucket can only be accessed through profile (profile can be set during Tibanna deployment)
      - ``rename`` if the file name must be changed upon download to the EC2 instance. This could be useful if your files are organized in certain names on S3 but the pipeline requires it to have a different name.
      - ``unzip`` to unzip the file during the upload to the EBS volume. Supported compression types are "gz" and "bz2".
      - ``mount`` to mount the input instead of downloading. This saves downloading time but may slow down the file reading slightly. The mounting is done at the bucket level to the EBS. We have tested up to 50 instances concurrently mounting the same bucket with no problem - if you're running 10,000 jobs, we cannot guarantee if this would still work. ``mount`` and ``rename`` cannot be used together. If another input file is specified without mount but from the same bucket, this other input file will be downloaded to the running instance even though the bucket is mounted.

    - ``object_key`` and ``rename`` can be a singleton, an array, an array of arrays or an array of arrays of arrays.
    - (e.g.

    ::

        {
            "bam": {
                "bucket_name": "montys-data-bucket",
                "object_key": "dataset1/sample1.bam",
                "mount": true
            },
            "chromsize": {
                "bucket_name": "montys-data-bucket",
                "object_key": "references/JKGFALIFVG.chrom.sizes"
                'rename': 'some_dir_on_ec2/hg38.chrom.sizes'
            }
        }

    )

    - key can be a target file path (to be used inside container run environment) starting with
      ``file://`` instead of CWL/WDL argument name.

      - Input data can only be downloaded to ``/data1/input`` or ``/data1/<language_name>`` where
        ``<language_name`` is ``cwl|wdl|shell|snakemake``.  The latter ``/data1/<language_name>``
        is the working directory for ``snakemake`` and ``shell``.
      - It is highly recommended to stick to using only argument names for CWL/WDL for pipeline
        reproducibility, since they are already clearly defined in CWL/WDL (especially for CWL).
      - (e.g.

      ::

          {
              "file:///data1/shell/mysample1.bam": {
                  "bucket_name": "montys-data-bucket",
                  "object_key": "dataset1/sample1.bam"
              }
          }


:secondary_files:
    - A dictionary of the same format as `input_file` but contains secondary files.
    - The keys must match the input argument name of the CWL/WDL where the secondary file belongs.
    - (e.g.

    ::

        {
            "bam": {
                "bucket_name": "montys-data-bucket",
                "object_key": "dataset1/sample1.bam.bai"
            }
        }

    )


:input_parameters:
    - A dictionary that contains input parameter values. Default parameters don't need to be included. The keys must match the input argument name of the CWL/WDL.
    - (e.g.

    ::

        {
            'nThreads': 16
        }

    )


:input_env:
    - A dictionary that specifies environment variables to be passed.
    - Do not use this feature to pass in AWS_ACCESS_KEY and/or AWS_SECRET_KEY or AWS_REGION - it will interfere with the bucket permission of the instance.
    - (e.g.

    ::

        {
            "TEST_ENV_VAR": "abcd"
        }

    )


Output target specification
###########################


:output_S3_bucket:
    - The name of the bucket where output files will be sent to.

:output_target:
    - A dictionary that contains a desired object keys to be put inside output bucket. This can be useful if, for example, the pipeline always generates an output file of the same name (e.g. report, output.txt, etc) but the user wants to distinguish them by sample names in the output bucket. If not set, the original output file names will be used as object key.
    - (e.g.

    ::

        {
          "out_pairsam": "output/dataset1/sample1.sam.pairs.gz"
        }

    )

    - key can be a source file path (to be used inside container run environment) starting with
      ``file://`` instead of CWL/WDL argument name.

    - (e.g.

    ::

        {
          "file:///data1/out/some_random_output.txt": "output/some_random_output.txt"
        }

    - It is highly recommended to stick to using only argument names for CWL/WDL for pipeline
      reproducibility, since they are already clearly defined in CWL/WDL (especially for CWL).

    - Starting with version ``1.0.0``, a dictionary format is also accepted for individual target, with keys ``object_key`` ``bucket_name``, ``object_prefix`` and/or  ``unzip``. For a regular file output, ``object_key`` and ``bucket_name`` can be used. The use of ``bucket_name`` here allows using a different output bucket for specific output files. For a directory, ``object_prefix`` can be used instead which will be used as if it is the directory name on S3. ``object_prefix`` may or may not have the trailing ``/``. ``unzip`` is boolean (either ``true`` or ``false``) and can be applied to a case when the output file is a ``zip`` file and you want the content to be extracted into a directory on an S3 bucket.

    - (e.g.

    ::

        {
            "out_pairsam": {
               "object_key": "output/renamed_pairsam_file"
            }
        }

    ::

        {
            "out_pairsam": {
               "object_key": "output/renamed_pairsam_file",
               "bucket_name" : "some_different_bucket"
            }
        }

    ::

        {
            "some_output_as_dir": {
                "object_prefix": "some_dir_output/",
                "bucket_name": "some_different_bucket"
            }
        }

    ::

        {
           "out_zip": {
              "object_prefix": "zip_output/",
              "unzip": true
        }

    - One or multiple tags can be automatically added to each ouput file by specifying the ``tag`` key. In the following example, two (object-level) tags are added to the result file. Note that the tag-set must be encoded as URL Query parameters. In case the ``unzip`` key is specified in addition to the ``tag`` key, each file in the output directory will be tagged.

    ::

        {
           "out_zip": {
              "object_key": "result.txt",
              "tag": "Key1=Value1&Key2=Value2"
        }


:secondary_output_target:
    - Similar to ``output_target`` but for secondary files.
    - (e.g.

    ::

        {
          "out_pairsam": "output/dataset1/sample1.sam.pairs.gz.px2"
        }

    )

:alt_cond_output_argnames:
    - In case output argnames are conditional (see an example in simple_example_cond_merge_), specify a global output name that can point to one of the conditional outputs.
    - This applies only to WDL since CWL does not support conditional statements.
    - (e.g.

    ::

        'alt_cond_output_argnames' : {
          'merged' : ['cond_merged.paste.pasted', 'cond_merged.cat.concatenated']
        },
        'output_target': {
          'merged' : 'somedir_on_s3/somefilename'
        }


.. _simple_example_cond_merge: https://tibanna.readthedocs.io/en/latest/simple_example_merge.html


Dependency specification
########################


:dependency:
    - List of other jobs that should finish before the job starts
    - Currently, only execution arns are accepted. An execution arn of a given run is printed out after running the ``tibanna run_workflow`` command. It can also be retrieved from the response of the ``run_workflow`` function (``response['_tibanna']['exec_arn']``).

    ::

        {
            "exec_arn": ["arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default_7927:md5_test"]
        }


Custom error handling
#####################

:custom_errors:
    - List of dictionaries describing custom error types
    - This field allows users to define workflow-specific errors based on a string pattern in log. Tibanna CheckTask step will parse the logs and detect this error.
    - This does not serve as error detection - it serves as error identification once the run has failed.
    - If the matching error happens, you'll see the error type and the corresponding line(s) of the error in the log file printed as the Exception in Step function.
    - ``error_type`` is a short tag that defines the name of the error.
    - ``pattern`` is the regex pattern to be detected in the log.
    - ``multiline`` (optional) should be set True if ``pattern`` is multi-line (e.g. contains ``\n``).

    ::

        [
            {
                 "error_type": "Unmatching pairs in fastq"
                 "pattern": "paired reads have different names: .+",
                 "multiline": False
            }
        ]


config
------

The ``config`` field describes execution configuration.

:log_bucket:
    - <log_bucket_name>
    - This is where the logs of the Tibanna runs are sent to.
    - required

:instance_type:
    - <instance_type>
    - This or ``mem`` and ``cpu`` are required if Benchmark is not available for a given workflow.
    - If both ``instance_type`` and ``mem`` & ``cpu`` are specified, then ``instance_type`` is the first choice.

:mem:
    - <memory_in_gb>
    - required is Benchmark is not available for a given workflow and if ``instance_type`` is not specified.
    - ``mem`` specifies memory requirement - instance_type is auto-determined based on ``mem`` and ``cpu``.
    - Starting version 1.2.0, 1GB is added to mem when choosing an instance type by default. To turn off This
      automatic increase in memory, set ``mem_as_is`` to be ``true``.

:mem_as_is:
    - <true|false>
    - If true, the value set in ``mem`` is used as it is when choosing an instance type. If false, 1GB is added
      by default, to accommodate the memory consumption of the house-keeping processes.
    - This field is available for >=1.2.0

:cpu:
    - <number_of_cores>
    - required is Benchmark is not available for a given workflow and if ``instance_type`` is not specified.
    - ``cpu`` specifies number of cores required to run a given workflow  - instance_type is auto-determined
      based on ``mem`` and ``cpu``.

:ebs_size:
    - <ebs_size_in_gb>
    - The EBS volume size used for data (input, output, or any intermediary files). This volume is mounted as
      ``/data1`` on the EC2 instance and as ``/data1`` inside Docker image when running in the ``shell`` or
      ``snakemake`` mode.
    - 10 is minimum acceptable value.
    - set as 10 if not specified and if Benchmark is not available for a given workflow.
    - It can be provided in the format of ``<s>x`` (e.g. ``3x``, ``5.5x``) to request ``<s>`` times total input size.
      (or 10 is smaller than 10)
    - Starting version 1.2.0, 5GB is added to ebs_size by default. To turn off This automatic increase in EBS size,
      set ``ebs_size_as_is`` to be ``true``.

:ebs_size_as_is:
    - <true|false>
    - If true, the value set in ``ebs_size`` is used as it is. If false, 5GB is added
      by default, to accommodate the disk usage of the house-keeping processes and the docker image/containers.
    - This field is available for >=1.2.0

:EBS_optimized:
    - <ebs_optimized> ``true``, ``false`` or '' (blank)
    - required if Benchmark is not available for a given workflow.
    - Whether the specific instance type should be EBS_optimized. It can be True only for an instance type that
      can be EBS optimized. If instance type is unspecified, leave this as blank.

:root_ebs_size:
    - <root_ebs_size_in_gb>
    - default 8
    - For versions < ``1.0.0``, Tibanna uses two separate EBS volumes, one for docker image, another for data.
      Most of the times, the 8GB root EBS that is used for docker images has enough space. However, if the
      docker image is larger than 5GB or if multiple large docker images are used together, one may consider
      increasing root ebs size. Any directory that is used inside a docker image (e.g. ``/tmp`` when running
      in the ``shell`` mode) that is not mounted from the data EBS could also cause a ``no space left in device``
      error on the root EBS volume. It is recommended to use a directory under ``/data1`` as a temp directory
      when running in the ``shell`` mode, which is mounted from data EBS.
    - This field is supported in version ``0.9.0`` or higher. If an older version has been used, redeploy
      ``run_task_awsem`` to enable this feature, after installing ``0.9.0`` or higher, as below.

      ::

          tibanna deploy_core -n run_task_awsem -g <usergroup> [-s <suffix>]

    - For versions >= ``1.0.0``, this field is no longer needed (though still supported) since the docker image
      also uses the data EBS and not the root EBS starting ``1.0.0``. This means for a large docker image, it is
      recommended to increase ``ebs_size`` rather than ``root_ebs_size``. It takes effect only if ``run_task_awsem``
      is redeployed as above. For consistency, when you redeploy ``run_task_awsem`` from version < ``1.0.0`` to
      version >= ``1.0.0``, it is also recommended to redeploy ``check_task_awsem`` with the same version.


:shutdown_min:
    - either number of minutes or string 'now'
    - 'now' would make the EC2 instance to terminate immediately after a workflow run. This option saves cost if the pipeline is stable. If debugging may be needed, one could set shutdown_min to be for example, 30, in which case the instance will keep running for 30 minutes after completion of the workflow run. During this time, a user could ssh into the instance.
    - optional (default : "now")

:password:
    - <password_for_ssh> or '' (blank)
    - One can use either password or key_name (below) as ssh mechanism, if the user wants an option to ssh into the instance manually for monitoring/debugging purpose. Tibanna itself does not use ssh.
    - The password can be any string and anyone with the password and the ip address of the EC2 instance can ssh into the machine.
    - optional (default : no password-based ssh)

:key_name:
    - <key_pair_name> or '' (blank)
    - One can use either password (above) or key_name as ssh mechanism, if the user wants an option to ssh into the instance manually for monitoring/debugging purpose. Tibanna itself does not use ssh.
    - The key pair should be an existing key pair and anyone with the key pair ``.pem`` file and the ip address of the EC2 instance can ssh into the machine.
    - optional (default : no key-based ssh)

:ebs_iops:
    - IOPS of the io1 type EBS
    - optional (default: unset)

:ebs_type:
    - type of EBS (e.g. ``gp3``, ``gp2``, ``io1``)
    - optional (default: gp3 (version >= ``1.0.0``) or gp2 (version < ``1.0.0``))

:cloudwatch_dashboard:
    - **This option is now depricated.**
    - if true, Memory Used, Disk Used, CPU Utilization Cloudwatch metrics are collected into a single Cloudwatch Dashboard page. (default ``false``)
    - Warning: very expensive - Do not use it unless absolutely neessary.
      Cloudwatch metrics are collected for every awsem EC2 instances even if this option is turned off.
      The Dashboard option makes it easier to look at them together.
    - There is a limit of 1,000 CloudWatch Dashboards per account, so do not turn on this option for more than 1,000 runs.

:spot_instance:
    - if true, request spot instance instead of an On-Demand instance
    - optional (default ``false``)

:spot_duration:
    - Max duration of spot instance in min (no default). If set, request a fixed-duration spot instance instead of a regular spot instance. ``spot_instance`` must be set ``true``.
    - optional (no default)

:behavior_on_capacity_limit:
    - behavior when a requested instance type (or spot instance) is not available due to instance limit or unavailability.
    - available options :

      - ``fail`` (default)
      - ``wait_and_retry`` (wait and retry with the same instance type again),
      - ``other_instance_types`` top 10 cost-effective instance types will be tried in the order
                                 (``mem`` and ``cpu`` must be set in order for this to work),
      - ``retry_without_spot`` (try with the same instance type but not a spot instance) : this option is applicable only when
        ``spot_instance`` is set to ```True``

:availability_zone:
    - specify availability zone (by default, availability zone is randomly selected within region by AWS)
    - e.g. ``us-east-1a``
    - optional (no default)

:security_group:
    - specify security group. This feature may be useful to launch an instance to a specific VPC.
    - e.g. ``sg-00151073fdf57305f``
    - optional (no default)
    - This feature is supported in version `0.15.6` or higher. If an older version has been used, redeploy
      ``run_task_awsem`` to enable this feature, after installing ``0.15.6`` or higher, as below.

      ::

          tibanna deploy_core -n run_task_awsem -g <usergroup> [-s <suffix>]

:subnet:
    - specify subnet ID. This feature may be useful to launch an instance to a specific VPC. If you don't have default VPC, subnet must be specified.
    - e.g. ``subnet-efb1b3c4``
    - optional (no default)
    - This feature is supported in version `0.15.6` or higher. If an older version has been used, redeploy
      ``run_task_awsem`` to enable this feature, after installing ``0.15.6`` or higher, as below.

      ::

          tibanna deploy_core -n run_task_awsem -g <usergroup> [-s <suffix>]
