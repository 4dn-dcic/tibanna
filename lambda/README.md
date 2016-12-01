# lambda functions
Currently the following lambda functions work. (Many details need to change though)
* test_validatefiles3
* test_checkvalidatefiles


## test_validatefiles3
Mounts a set of files on 4dn S3 to sbg s3, launch a task on those files on SBG.
### input format
Example input for validatefiles
```
{
    "input_files": [
        {
          "bucket_name":"4dn-dcic-sbg",
          "object_key":"arrow7.jpg",
          "workflow_argument_name":"input_file"
        }
    ],
    "app_name": "validate",
    "parameters": {}
}

```

Example input for bwa-mem (alignment)
```
{
  "input_files": [
    {
      "bucket_name": "4dn-tool-evaluation-files",
      "object_key": "___GM12878_SRR1658581_1pc_1_R1.fastq",
      "workflow_argument_name": "fastq1"
    },
    {
      "bucket_name": "4dn-tool-evaluation-files",
      "object_key": "___GM12878_SRR1658581_1pc_1_R2.fastq",
      "workflow_argument_name": "fastq2"
    },
    {
      "bucket_name": "4dn-tool-evaluation-files",
      "object_key": "___hg19-0.7.13.bwaIndex.tgz",
      "workflow_argument_name": "bwa_index"
    }
  ],
  "app_name": "bwa-mem",
  "parameters": {
    "nThreads": 8
  }
}

```

### output format
Example output (succeeded). The 'id' field can be used as the 'task_id' input for test_checkvalidatefiles.
```
{
  "status": "QUEUED",
  "inputs": {
    "type": "fastq",
    "input_file": {
      "path": "583dff80e4b054ffd990a911",
      "class": "File",
      "name": "arrow7.jpg"
    }
  },
  "errors": [],
  "start_time": "2016-11-29T22:21:55Z",
  "name": "validatefiles run - 11-29-16 22:21:55",
  "warnings": [],
  "outputs": {
    "report": null
  },
  "app": "4dn-dcic/dev/validate/4",
  "batch": false,
  "created_by": "4dn-labor",
  "execution_status": {
    "message": "In queue"
  },
  "project": "4dn-dcic/dev",
  "href": "https://api.sbgenomics.com/v2/tasks/c245b984-3616-40ca-94d2-849c43c423ad",
  "executed_by": "4dn-labor",
  "type": "v2",
  "id": "c245b984-3616-40ca-94d2-849c43c423ad"
}
```

## test_checkvaliatefiles
Checks status of a task on SBG and if completed, export output to 4dn s3 and return workflow_run and processed_files metadata objects.
This lambda function is generic and not specifically applicable to validatefiles.

### input format
Example input
```
{
  "task_id":"c245b984-3616-40ca-94d2-849c43c423ad",
  "bucket_name":"4dn-dcic-sbg"
}
```

### output format

Example output while the workflow is still running
```
{
  "processed_files": [],
  "workflow": {
    "status": "RUNNING",
    "output_files": [],
    "uuid": "b46d34fc-49e5-4c33-afab-9ec90d65faf3",
    "parameters": [
      {
        "workflow_argument_name": "type",
        "value": "fastq"
      }
    ],
    "input_files": []
  }
}

```

Example output after task is done (file export may still be running)
In this example, an output file '_12_report' has been created and assigned uuid d897a651-49e5-4c33-afab-9ec90d65faf3 and exported to bucket 4dn-dcic-sbg. This output file corresponds to the output 'report' in the workflow. The workflow run is assigned uuid 72a65bb0-49e5-4c33-afab-9ec90d65faf3. Here, uuid's are randomly generated.

```
{
  "processed_files": [
    {
      "status": "export RUNNING",
      "submitted_by": "admin@admin.com",
      "uuid": "d897a651-49e5-4c33-afab-9ec90d65faf3",
      "award": "1U01CA200059-01",
      "file_format": "other",
      "notes": "sample dcic notes",
      "accession": "4DNFIB4P2S5F",
      "lab": "4dn-dcic-lab",
      "filename": "s3://4dn-dcic-sbg/_12_report"
    }
  ],
  "workflow_run": {
    "output_files": [
      {
        "workflow_argument_name": "report",
        "value": "d897a651-49e5-4c33-afab-9ec90d65faf3"
      }
    ],
    "uuid": "72a65bb0-49e5-4c33-afab-9ec90d65faf3",
    "parameters": [
      {
        "workflow_argument_name": "type",
        "value": "fastq"
      }
    ],
    "input_files": []
  }
}
```

Example output with output file export completed.
```
{
  "workflow_run": {
    "output_files": [
      {
        "workflow_argument_name": "report",
        "value": "7204bc0e-49e5-4c33-afab-9ec90d65faf3"
      }
    ],
    "uuid": "8de5a59e-49e5-4c33-afab-9ec90d65faf3",
    "parameters": [
      {
        "workflow_argument_name": "type",
        "value": "fastq"
      }
    ],
    "input_files": []
  },
  "processed_files": [
    {
      "status": "export COMPLETED",
      "submitted_by": "admin@admin.com",
      "uuid": "7204bc0e-49e5-4c33-afab-9ec90d65faf3",
      "award": "1U01CA200059-01",
      "file_format": "other",
      "notes": "sample dcic notes",
      "accession": "4DNFUJD37IHA",
      "lab": "4dn-dcic-lab",
      "filename": "s3://4dn-dcic-sbg/_13_report"
    }
  ]
}
```

Example output from a Hi-C_processing_partA run (producing four output files)
```
{
  "workflow_run": {
    "output_files": [
      {
        "workflow_argument_name": "out_pairs_index",
        "value": "5caaa69e-49e5-4c33-afab-9ec90d65faf3"
      },
      {
        "workflow_argument_name": "out_sorted_bam_index",
        "value": "49b5dc2e-49e5-4c33-afab-9ec90d65faf3"
      },
      {
        "workflow_argument_name": "out_sorted_bam",
        "value": "1c76dd19-49e5-4c33-afab-9ec90d65faf3"
      },
      {
        "workflow_argument_name": "out_pairs",
        "value": "281cef36-49e5-4c33-afab-9ec90d65faf3"
      }
    ],
    "uuid": "bcfbc3f0-49e5-4c33-afab-9ec90d65faf3",
    "parameters": [],
    "input_files": []
  },
  "processed_files": [
    {
      "status": "export COMPLETED",
      "submitted_by": "admin@admin.com",
      "uuid": "5caaa69e-49e5-4c33-afab-9ec90d65faf3",
      "award": "1U01CA200059-01",
      "file_format": "other",
      "notes": "sample dcic notes",
      "accession": "4DNF4ZG16SPQ",
      "lab": "4dn-dcic-lab",
      "filename": "s3://4dn-dcic-sbg/_1_out.bsorted.pairs.gz.px2"
    },
    {
      "status": "export COMPLETED",
      "submitted_by": "admin@admin.com",
      "uuid": "49b5dc2e-49e5-4c33-afab-9ec90d65faf3",
      "award": "1U01CA200059-01",
      "file_format": "other",
      "notes": "sample dcic notes",
      "accession": "4DNFRZBPHGIF",
      "lab": "4dn-dcic-lab",
      "filename": "s3://4dn-dcic-sbg/out.sorted.bam.bai"
    },
    {
      "status": "export COMPLETED",
      "submitted_by": "admin@admin.com",
      "uuid": "1c76dd19-49e5-4c33-afab-9ec90d65faf3",
      "award": "1U01CA200059-01",
      "file_format": "other",
      "notes": "sample dcic notes",
      "accession": "4DNFROXPB21J",
      "lab": "4dn-dcic-lab",
      "filename": "s3://4dn-dcic-sbg/_1_out.sorted.bam"
    },
    {
      "status": "export COMPLETED",
      "submitted_by": "admin@admin.com",
      "uuid": "281cef36-49e5-4c33-afab-9ec90d65faf3",
      "award": "1U01CA200059-01",
      "file_format": "other",
      "notes": "sample dcic notes",
      "accession": "4DNF6TUAVFQI",
      "lab": "4dn-dcic-lab",
      "filename": "s3://4dn-dcic-sbg/_1_out.bsorted.pairs.gz"
    }
  ]
}
```
