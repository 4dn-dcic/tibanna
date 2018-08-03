from uuid import uuid4
from dcicutils.ff_utils import (
    generate_rand_accession,
    get_authentication_with_server,
    post_metadata,
    get_metadata,
    patch_metadata
)
from core.utils import run_workflow
from core.pony_utils import get_wfr_uuid
import gzip
import boto3
import time


def post_random_file(bucket, ff_key):
    """Generates a fake pairs.gz file with random uuid and accession
    and posts it to fourfront. The content is unique since it contains
    its own uuid. The file metadata does not contain md5sum or
    content_md5sum.
    Uses the given fourfront keys
    """
    uuid = str(uuid4())
    accession = generate_rand_accession()
    newfile = {
      "accession": accession,
      "file_format": "pairs",
      "award": "b0b9c607-f8b4-4f02-93f4-9895b461334b",
      "lab": "828cd4fe-ebb0-4b36-a94a-d2e3a36cc989",
      "uuid": uuid,
      "extra_files": [
         {
           "file_format": "pairs_px2",
           "accession": accession,
           "uuid": uuid
         }
      ]
    }
    upload_key = uuid + '/' + accession + '.pairs.gz'
    tmpfilename = 'alsjekvjf.gz'
    with gzip.open(tmpfilename, 'wb') as f:
        f.write(uuid)
    extra_upload_key = uuid + '/' + accession + '.pairs.gz.px2'
    extra_tmpfilename = 'alsjekvjf-extra.gz'
    with gzip.open(extra_tmpfilename, 'wb') as f:
        f.write(uuid + '.px2')
    response = post_metadata(newfile, 'file_processed', key=ff_key)
    print(response)
    s3 = boto3.resource('s3')
    s3.meta.client.upload_file(tmpfilename, bucket, upload_key)
    s3.meta.client.upload_file(extra_tmpfilename, bucket, extra_upload_key)
    return newfile


def testrun_md5_input_json_w_extra_file_object_name(workflow_name='tibanna_pony', env='webdev'):
    """Creates a random file object with no md5sum/content_md5sum and run md5 workflow.
    It waits for 6 mintues till the workflow run finishes and checks the input file object
    has been updated.
    """
    bucket = "elasticbeanstalk-fourfront-" + env + "-wfoutput"
    ff_key = get_authentication_with_server(ff_env='fourfront-' + env)
    newfile = post_random_file(bucket, ff_key)
    uuid = newfile['uuid']
    accession = newfile['accession']
    wf_uuid = "c77a117b-9a58-477e-aaa5-291a109a99f6"
    input_json = {
        "config": {
          "ebs_type": "io1",
          "ebs_iops": 500,
          "s3_access_arn": "arn:aws:iam::643366669028:instance-profile/S3_access",
          "ami_id": "ami-cfb14bb5",
          "json_bucket": "4dn-aws-pipeline-run-json",
          "shutdown_min": 30,
          "copy_to_s3": True,
          "launch_instance": True,
          "log_bucket": "tibanna-output",
          "script_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/",
          "key_name": "4dn-encode",
          "password": ""
        },
        "_tibanna": {
          "env": "fourfront-webdev",
          "run_type": "md5"
        },
        "parameters": {},
        "app_name": "md5",
        "workflow_uuid": wf_uuid,
        "input_files": [
                        {"workflow_argument_name": "input_file",
                         "bucket_name": bucket,
                         "uuid": uuid,
                         "object_key": accession + '.pairs.gz.px2',
                         "format_if_extra": "pairs_px2"
                         }
        ],
        "output_bucket": bucket,
        "wfr_meta": {"notes": "extra file md5 trigger test from test_webdev.py"}
    }
    resp = run_workflow(input_json, workflow=workflow_name)
    print(resp)

    # check result
    time.sleep(6*60)  # wait for 6 minutes
    filemeta = get_metadata(uuid, key=ff_key, add_on='?datastore=database')
    content_md5sum = filemeta.get('extra_files')[0].get('content_md5sum')
    md5sum = filemeta.get('extra_files')[0].get('md5sum')
    wfr_uuid = get_wfr_uuid(resp['_tibanna']['exec_arn'])
    wfr_meta = get_metadata(wfr_uuid, key=ff_key, add_on='?datastore=database')
    assert 'input_files' in wfr_meta
    assert 'input_file' in wfr_meta['input_files']
    assert 'format_if_extra' in wfr_meta['input_files']['input_file']
    assert md5sum
    assert content_md5sum
    print(content_md5sum)
    print(md5sum)
    patch_metadata({'status': 'deleted'}, uuid, key=ff_key)


def testrun_md5(workflow_name='tibanna_pony', env='webdev'):
    """Creates a random file object with no md5sum/content_md5sum and run md5 workflow.
    It waits for 6 mintues till the workflow run finishes and checks the input file object
    has been updated.
    """
    bucket = "elasticbeanstalk-fourfront-" + env + "-wfoutput"
    ff_key = get_authentication_with_server(ff_env='fourfront-' + env)
    newfile = post_random_file(bucket, ff_key)
    uuid = newfile['uuid']
    accession = newfile['accession']
    input_json = {
        "config": {
          "ebs_type": "io1",
          "ebs_iops": 500,
          "s3_access_arn": "arn:aws:iam::643366669028:instance-profile/S3_access",
          "ami_id": "ami-cfb14bb5",
          "json_bucket": "4dn-aws-pipeline-run-json",
          "shutdown_min": 30,
          "copy_to_s3": True,
          "launch_instance": True,
          "log_bucket": "tibanna-output",
          "script_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/",
          "key_name": "4dn-encode",
          "password": ""
        },
        "_tibanna": {
          "env": "fourfront-webdev",
          "run_type": "md5"
        },
        "parameters": {},
        "app_name": "md5",
        "workflow_uuid": "c77a117b-9a58-477e-aaa5-291a109a99f6",
        "input_files": [
                        {"workflow_argument_name": "input_file",
                         "bucket_name": bucket,
                         "uuid": uuid,
                         "object_key": accession + '.pairs.gz'
                         }
        ],
        "output_bucket": bucket,
        "wfr_meta": {"notes": "processed file md5 trigger test from test_webdev.py"}
    }
    resp = run_workflow(input_json, workflow=workflow_name)
    print(resp)

    # check result
    time.sleep(6*60)  # wait for 6 minutes
    filemeta = get_metadata(uuid, key=ff_key, add_on='?datastore=database')
    assert 'md5sum' in filemeta
    assert 'content_md5sum' in filemeta
    content_md5sum = filemeta.get('content_md5sum')
    md5sum = filemeta.get('md5sum')
    assert md5sum
    assert content_md5sum
    print(content_md5sum)
    print(md5sum)
    patch_metadata({'status': 'deleted'}, uuid, key=ff_key)
