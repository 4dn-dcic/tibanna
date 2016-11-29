# lambda functions
Currently the following lambda functions work.
* test_validatefiles2
* test_checkvalidatefiles


## test_validatefiles2
Mounts a file on 4dn S3 to sbg s3, launch a validatefiles task on that file on SBG.
### input format
Example input
```
{
  "bucket_name": "4dn-dcic-sbg",
  "object_key": "arrow7.jpg"
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
  "workflow": {
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

