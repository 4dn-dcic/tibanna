=====================
Execution JSON Schema
=====================

The input json defines an individual execution. It has two parts, `args` and `config`. `args` contains information about pipeline, input files, output bucket, input parameters, etc. `config` has parameters about AWS such as instance type, EBS size, ssh password, etc.


args
----


config
------

:ebs_size:
    <ebs_size_in_gb>
    it can be specified by the user or left to be 0 (auto-determine) if Benchmark function is available for a given workflow/pipeline.

:log_bucket:
    <log_bucket_name>
    This is where the logs of the Tibanna runs are sent to.

:json_bucket:
    <log_bucket_name>
    This is where Tibanna sends an instruction to for an AWSEM EC2 instance.

:instance_type:
    <instance_type>
    Instance type (e.g. t2.micro) can be specified by the user or left to be '' (auto-determine) if Benchmark function is available for a given workflow.

:EBS_optimized:
    <ebs_optimized> ``true``, ``false`` or '' (blank)
    Whether the specific instance type should be EBS_optimized. It can be True only for an instance type that can be EBS optimized. If instance type is unspecified, leave this as blank.

:shutdown_min: either number of minutes or string 'now'
    'now' would make the EC2 instance to terminate immediately after a workflow run. This option saves cost if the pipeline is stable. If debugging may be needed, one could set shutdown_min to be for example, 30, in which case the instance will keep running for 30 minutes after completion of the workflow run. During this time, a user could ssh into the instance.

:password:
    <password_for_ssh> or '' (blank)
    One can use either password or key_name (below) as ssh mechanism, if the user wants an option to ssh into the instance manually for monitoring/debugging purpose. Tibanna itself does not use ssh.
    The password can be any string and anyone with the password and the ip address of the EC2 instance can ssh into the machine.

:key_name:
    <key_pair_name> or '' (blank)
    One can use either password (above) or key_name as ssh mechanism, if the user wants an option to ssh into the instance manually for monitoring/debugging
purpose. Tibanna itself does not use ssh.
    The key pair should be an existing key pair and anyone with the key pair ``.pem`` file and the ip address of the EC2 instance can ssh into the machine.

:ebs_iops: 500
:ebs_type: io1
:copy_to_s3: ``true``
:launch_instance: ``true``



Example input json
------------------

::

    {
      "config": {
        "ebs_size": 0,
        "json_bucket": "suwang",
        "EBS_optimized": "",
        "ebs_iops": 500,
        "shutdown_min": 30,
        "instance_type": "",
        "ebs_type": "io1",
        "copy_to_s3": true,
        "launch_instance": true,
        "password": "whateverpasswordworks",
        "log_bucket": "suwang",
        "key_name": ""
      },
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
      }
    }


Create an input json file similar to the above content, replace output ('output_target') and input file names and 'ebs_size'. The 'ebs_size' should be in GB and if it is set to 0, it will be auto-determined by the benchmark function. Likewise, 'instance_type' and 'EBS_optimized' can be set to be "", which allows the Benchmark function to auto-determine these parameters. One could override it by specifically assigning values to these fields (e.g. "EBS_optimized": true, "instance_type": "c2.xlarge", "ebs_size": 500). For a high IO performance, it is recommended to use "ebs_iops" to be higher (e.g. 20000), but 500 should be fine for regular jobs. More examples are in test_json/suwang*json.

