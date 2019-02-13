===================================
Running 4DN pipelines using Tibanna
===================================

* For 4DN pipelines, benchmark functions are pre-implemented in Tibanna through the Benchmark package. This means that the user does not have to choose EC2 instance type or EBS size (they are auto-determined). Use the following blank values for these config fields. The user may choose specific instance type or EBS size if needed.

::

      "config": {
        "instance_type": "",
        "ebs_size": 0,
        "EBS_optimized": "",


General Quality Control
+++++++++++++++++++++++

md5
---

* Description : calculates two md5sum values (one the file itself, one for ungzipped) for an input file. If the input file is not gzipped, it reports only the first one.
* CWL : https://github.com/4dn-dcic/pipelines-cwl/blob/dev/cwl_awsem_v1/md5.cwl
* Docker : ``duplexa/md5:v2``
* 4DN workflow metadata : https://data.4dnucleome.org/4dn-dcic-lab:wf-md5-0.2.6
* 4DN example run: https://data.4dnucleome.org/workflow-runs-awsem/75ce5f66-f98f-4222-9d1c-3daed262856b/#graph

|md5_4dn_run|

.. |md5_4dn_run| image:: images/md5_4dn_run.png


* Run using tibanna :

::

    invoke run_workflow --input-json=<input_json>


* Example input execution json :

Use the following as a template and replace ``<YOUR....>`` with your input/output/log bucket/file(object) informatio.n

::

    {
      "args": {
        "app_name": "md5",
        "app_version": "0.2.6",
        "cwl_directory_url": "https://raw.githubusercontent.com/4dn-dcic/pipelines-cwl/0.2.6/cwl_awsem/",
        "cwl_version": "v1",
        "cwl_main_filename": "md5.cwl",
        "cwl_child_filenames": [],
        "input_files": {
          "input_file": {
            "bucket_name": "<YOUR_INPUT_BUCKET>",
            "object_key": "<YOUR_INPUT_FILE_NAME_IN_INPUT_BUCKET>"
          }
        },
        "input_parameters": {},
        "secondary_files": {},
        "output_S3_bucket": "<YOUR_OUTPUT_BUCKET>",
        "output_target": {
          "report": "<YOUR_OUTPUT_FILE_NAME_IN_OUTPUT_BUCKET>"
        },
        "secondary_output_target": {}
      },
      "config": {
        "instance_type": "",
        "ebs_size": 0,
        "EBS_optimized": "",
        "ebs_type": "io1",
        "ebs_iops": 500,
        "shutdown_min": "now",
        "password": "",
        "log_bucket": "<YOUR_LOG_BUCKET>",
        "key_name": "<YOUR_KEY_NAME>"
      }
    }



fastqc
------

* Description : run fastqc on a fastq file



Hi-C data processing & QC
+++++++++++++++++++++++++

bwa-mem
-------

hi-c-processing-bam
-------------------

hi-c-processing-pairs
---------------------

pairsqc
-------

Repli-seq data processing & QC
++++++++++++++++++++++++++++++

repliseq-parta
--------------

ChIP-seq data processing & QC
+++++++++++++++++++++++++++++

encode-chipseq-aln-chip
-----------------------

encode-chipseq-aln-ctl
----------------------

encode-chipseq-postaln
----------------------

ATAC-seq data processing & QC
+++++++++++++++++++++++++++++

encode-atacseq-aln
------------------

encode-atacseq-postaln
----------------------


