# lambda-api for tibanna/SBG

## Table of Contents
* [Deploying Lambda](#deploying-lambda)
* [Usage](#usage)
* [Run call](#run-call)
* [Examples](#examples)


## Deploying Lambda
The lambda-API is created as follows:

```
cd /Users/soo/git/tibanna
chalice new-project lambda-api
#virtualenv lambda-api  ## this breaks git
cd lambda-api
# prepare for app.py, requirements.txt and .chalice/config.json
#source bin/activate  ## don't use venv
pip install -r requirements.txt --upgrade
chalice deploy  # deployment requires security credentials.
```

## Usage
```
## Run call
## running a workflow
http POST https://$API_ID.execute-api.us-east-1.amazonaws.com/dev/run < ../test_json/test_input_requestbody_launch_workflow_run_sbg.json

## Export call
## checking status and exporting the output file (the task_id should be valid and once the file is exported you can't run it again.)
http POST https://$API_ID.execute-api.us-east-1.amazonaws.com/dev/export < ../test_json/test_input_requestbody_export_sbg.json
```

Note: the tests work only when the input file import from a previous run using the same input files is removed from SBG.
(contact soo to get endpoint uri)


## Run call
* mounts/imports input files from s3 and launch a task in SBG.
* updates metadata schema for workflow_run_sbg, using fdnDCIC.


## Examples

* Example command for md5
```
http POST https://$API_ID.execute-api.us-east-1.amazonaws.com/dev/run < ../test_json/test_input_requestbody_launch_workflow_run_sbg.json
```
* output
```
HTTP/1.1 200 OK
Connection: keep-alive
Content-Length: 1579
Content-Type: application/json
Date: Wed, 14 Dec 2016 20:30:51 GMT
Via: 1.1 1d8d5028e8ee1abdfc063008966dcceb.cloudfront.net (CloudFront)
X-Amz-Cf-Id: tZ6mGQL158_acK_fc3f9V2MxfMcUPtactxmsENxw2bUYVTk8xu87ig==
X-Amzn-Trace-Id: Root=1-5851abef-b3c6f00aadbf321bafb18efb
X-Cache: Miss from cloudfront
x-amzn-RequestId: 2d2def1b-c23c-11e6-981a-c109eff27b05

{
    "metadata_object": {
        "@graph": [
            {
                "@id": "/workflow-runs-sbg/fa48dc3f-49e5-4c33-afab-9ec90d65faf3/",
                "@type": [
                    "WorkflowRunSbg",
                    "Item"
                ],
                "aliases": [],
                "award": "/awards/1U01CA200059-01/",
                "date_created": "2016-12-14T20:30:51.595289+00:00",
                "documents": [],
                "input_files": [
                    {
                        "value": "/files-fastq/4DNFI067AFHV/",
                        "workflow_argument_name": "input_file"
                    }
                ],
                "lab": "/labs/4dn-dcic-lab/",
                "parameters": [],
                "run_platform": "SBG",
                "run_status": "started",
                "sbg_export_ids": [],
                "sbg_import_ids": [
                    "ibiuGApowYnUldWZw7RvcKvhezUuNSZY"
                ],
                "sbg_mounted_volume_ids": [
                    "4dn-labor/4dn_s36ipevhen"
                ],
                "sbg_task_id": "c301430c-5e72-435b-a333-07319eeb5e4d",
                "schema_version": "1",
                "status": "in review by lab",
                "submitted_by": "/users/986b362f-4eb6-4a9c-8173-3ab267307e3a/",
                "title": "md5 run 2016-12-14 20:30:51.409996",
                "uuid": "fa48dc3f-49e5-4c33-afab-9ec90d65faf3",
                "workflow": "/workflows/d3f25cd3-e726-4b3c-a022-48f844474b41/"
            }
        ],
        "@type": [
            "result"
        ],
        "status": "success"
    },
    "sbg_task": {
        "app": "4dn-dcic/dev/md5/1",
        "batch": false,
        "created_by": "4dn-labor",
        "errors": [],
        "executed_by": "4dn-labor",
        "execution_status": {
            "message": "In queue"
        },
        "href": "https://api.sbgenomics.com/v2/tasks/c301430c-5e72-435b-a333-07319eeb5e4d",
        "id": "c301430c-5e72-435b-a333-07319eeb5e4d",
        "inputs": {
            "input_file": {
                "class": "File",
                "name": "4DNFI067AFHV.fastq.gz",
                "path": "5851abf5e4b02f902108b63b",
                "size": 46335351
            }
        },
        "name": "md5 run - 12-14-16 20:30:48",
        "outputs": {
            "report": null
        },
        "project": "4dn-dcic/dev",
        "start_time": "2016-12-14T20:30:48Z",
        "status": "QUEUED",
        "type": "v2",
        "warnings": []
    }
}
```

Another example command, for hic-processing-parta:
```
http POST https://$API_ID.execute-api.us-east-1.amazonaws.com/dev/run < ../test_json/test_input_requestbody_launch_workflow_run_sbg_2.json
```
* output:
```
HTTP/1.1 200 OK
Connection: keep-alive
Content-Length: 2304
Content-Type: application/json
Date: Wed, 14 Dec 2016 23:30:26 GMT
Via: 1.1 9618583567a38a34167f23464ee60537.cloudfront.net (CloudFront)
X-Amz-Cf-Id: tr2ghshKL25tQZaLvPFrVulgWpe7Joc8uDzp2vYJNbQQVxfVHWSbSA==
X-Amzn-Trace-Id: Root=1-5851d601-f1acdfcf332cc0fcdfd181bd
X-Cache: Miss from cloudfront
x-amzn-RequestId: 40873411-c255-11e6-8ac0-e1e13c91ebf2

{
    "metadata_object": {
        "@graph": [
            {
                "@id": "/workflow-runs-sbg/fa2f3ec5-49e5-4c33-afab-9ec90d65faf3/",
                "@type": [
                    "WorkflowRunSbg",
                    "Item"
                ],
                "aliases": [],
                "award": "/awards/1U01CA200059-01/",
                "date_created": "2016-12-14T23:30:26.535562+00:00",
                "documents": [],
                "input_files": [
                    {
                        "value": "/files-fastq/4DNFI067AFHV/",
                        "workflow_argument_name": "fastq1"
                    },
                    {
                        "value": "/files-fastq/4DNFI067AFHX/",
                        "workflow_argument_name": "fastq2"
                    },
                    {
                        "value": "/files-reference/4DNFIZQZ39L9/",
                        "workflow_argument_name": "bwa_index"
                    }
                ],
                "lab": "/labs/4dn-dcic-lab/",
                "parameters": [
                    {
                        "value": "8",
                        "workflow_argument_name": "nThreads"
                    }
                ],
                "run_platform": "SBG",
                "run_status": "started",
                "sbg_export_ids": [],
                "sbg_import_ids": [
                    "Jvl75ambeVjmBjrECpYDLCMrTflNuADx",
                    "Jv66i0w03G772IHed2VB9PdL8hyeQVpW",
                    "pSaCnCJJVVMpZ6IyLNMaU7NybvCDGHo5"
                ],
                "sbg_mounted_volume_ids": [
                    "4dn-labor/4dn_s34y3gmtp5",
                    "4dn-labor/4dn_s3idvi1ua2",
                    "4dn-labor/4dn_s3nnrnog99"
                ],
                "sbg_task_id": "a1e80a24-47d6-43d9-911f-7efda5d2988b",
                "schema_version": "1",
                "status": "in review by lab",
                "submitted_by": "/users/986b362f-4eb6-4a9c-8173-3ab267307e3a/",
                "title": "hi-c-processing-parta run 2016-12-14 23:30:26.367089",
                "uuid": "fa2f3ec5-49e5-4c33-afab-9ec90d65faf3",
                "workflow": "/workflows/02d636b9-d82d-4da9-950c-2ca994a0943e/"
            }
        ],
        "@type": [
            "result"
        ],
        "status": "success"
    },
    "sbg_task": {
        "app": "4dn-dcic/dev/hi-c-processing-parta/9",
        "batch": false,
        "created_by": "4dn-labor",
        "errors": [],
        "executed_by": "4dn-labor",
        "execution_status": {
            "message": "In queue"
        },
        "href": "https://api.sbgenomics.com/v2/tasks/a1e80a24-47d6-43d9-911f-7efda5d2988b",
        "id": "a1e80a24-47d6-43d9-911f-7efda5d2988b",
        "inputs": {
            "bwa_index": {
                "class": "File",
                "name": "4DNFIZQZ39L9.bwaIndex.tgz",
                "path": "5851d60ce4b0f31cb3c00c54",
                "size": 3445308903
            },
            "fastq1": {
                "class": "File",
                "name": "4DNFI067AFHV.fastq.gz",
                "path": "5851d605e4b0f31cb3c00c46",
                "size": 46335351
            },
            "fastq2": {
                "class": "File",
                "name": "4DNFI067AFHX.fastq.gz",
                "path": "5851d609e4b0f31cb3c00c4a",
                "size": 49961707
            },
            "nThreads": 8
        },
        "name": "Hi-C_processing_partA run - 12-14-16 23:30:23",
        "outputs": {
            "out_pairs": null,
            "out_pairs_index": null,
            "out_sorted_bam": null,
            "out_sorted_bam_index": null
        },
        "project": "4dn-dcic/dev",
        "start_time": "2016-12-14T23:30:23Z",
        "status": "QUEUED",
        "type": "v2",
        "warnings": []
    }
}

```

