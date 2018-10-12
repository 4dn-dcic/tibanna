=========================
Tibanna Pony for 4DN-DCIC
=========================

Tibanna Pony is an extension of Tibanna Unicorn used specifically for 4DN-DCIC. Pony has two additional steps that communicate with the 4DN Data Portal and handle 4DN metadata. Pony is only for 4DN-DCIC and requires access keys to the Data Portal and the 4DN DCIC AWS account.


=================  ==============
 Tibanna Unicorn    Tibanna Pony
=================  ==============
|tibanna_unicorn|  |tibanna_pony|
=================  ==============

.. |tibanna_unicorn| image:: images/screenshot_tibanna_unicorn.png
.. |tibanna_pony| image:: images/screenshot_tibanna_pony.png


Example Tibanna setup for 4DN-DCIC
----------------------------------

To deploy pony, you could do the following. (already done)

::

    invoke setup_tibanna_env --buckets=elasticbeanstalk-fourfront-webdev-files,elasticbeanstalk-fourfront-webdev-wfoutput,tibanna-output,4dn-aws-pipeline-run-json




Webdev testing for Pony
-----------------------

For full tibanna test (actually running jobs through step function) besides travis test, the following input json files are used.

::

    test_json/pony/awsem_md5.json  
    test_json/pony/awsem_fastqc.json
    test_json/pony/awsem_bwa_new.json
    test_json/pony/awsem_pairsqc.json
    test_json/pony/awsem_hicpairs_easy.json
    test_json/pony/awsem_hic_processing_bam-2.pony.json
    test_json/pony/awsem_repliseq_parta-pony.json

- note: these files are listed in ``tests/webdevtestlist``. One could use this file for batch testing for a given tibanna pony instance like an example below for Mac (replace tibanna_pony_uno with your step function mame).



::

    cat tests/webdevtestlist | xargs -I{} sh -c "invoke run_workflow --workflow=tibanna_pony_dev --input-json={}"

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


