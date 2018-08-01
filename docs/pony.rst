=========================
Tibanna Pony for 4DN-DCIC
=========================

Webdev testing for Pony
-----------------------

::

    test_json/awsem_md5.json  
    test_json/awsem_fastqc.json
    test_json/awsem_bwa_new.json
    test_json/awsem_pairsqc.json
    test_json/awsem_hicpairs_easy.json
    test_json/awsem_hic_processing_bam-2.pony.json
    test_json/awsem_repliseq_parta-pony.json

- note: these files are listed in webdevtestlist. One could use this file for batch testing for a given tibanna pony instance like an example below for Mac (replace tibanna_pony_uno with your step function mame).



::

    cat webdevtestlist | xargs -I{} sh -c "invoke run_workflow --workflow=tibanna_pony_uno --input-json={}"

Example Input Json for Pony
---------------------------

::

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
      },
      "wfr_meta": {
        "notes": "a nice workflow run"
      },
      "push_error_to_end": true
      "dependency": {
        "exec_arn": [
            "arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default_7412:md5_test",
            "arn:aws:states:us-east-1:643366669028:execution:tibanna_unicorn_default_7412:md5_test2"
        ]
      }
    }

- The ``app_name`` field contains the name of the workflow.
- The ``output_bucket`` field specifies the bucket where all the output files go to.
- The ``workflow_uuid`` field contains the uuid of the 4DN workflow metadata.
- The ``parameters`` field contains a set of workflow-specific parameters in a dictionary.
- The ``input_files`` field specifies the argument names (matching the names in CWL), the input file metadata uuid and its bucket and object key name.
- The ``config`` field is directly passed on to the second step, where instance_type, ebs_size, EBS_optimized are auto-filled, if not given.
- The ``custom_pf_fields`` field (optional) contains a dictionary that can be directly passed to the processed file metadata. The key may be either ``ALL`` (applies to all processed files) or the argument name for a specific processed file (or both).
- The ``wfr_meta`` field (optional) contains a dictionary that can be directly passed to the workflow run metadata.
- The ``push_error_to_end`` field (optional), if set true, passes any error to the last step so that the metadata can be updated with proper error status. (default true)
- The ``dependency`` field (optional) sets dependent jobs. The job will not start until the dependencies successfully finish. If dependency fails, the current job will also fail. The ``exec_arn`` is the list of step function execution arns. The job will wait at the run_task_awsem step, not at the start_task_awsem step (for consistenty with unicorn). This field will be passed to run_task_awsem as ``dependency`` inside the ``args`` field.

