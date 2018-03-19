from uuid import uuid4
from core.ff_utils import generate_rand_accession
from core.utils import run_workflow
import gzip
import boto3
from wranglertools import fdnDCIC
import time


def post_random_file(bucket, keypairs_file):
    """Generates a fake pairs.gz file with random uuid and accession
    and posts it to fourfront. The content is unique since it contains
    its own uuid. The file metadata does not contain md5sum or
    content_md5sum.
    """
    uuid = str(uuid4())
    accession = generate_rand_accession()
    newfile = {
      "accession": accession,
      "file_format": "pairs",
      "award": "b0b9c607-f8b4-4f02-93f4-9895b461334b",
      "lab": "828cd4fe-ebb0-4b36-a94a-d2e3a36cc989",
      "uuid": uuid
    }

    upload_key = uuid + '/' + accession + '.pairs.gz'
    tmpfilename = 'alsjekvjf.gz'
    with gzip.open(tmpfilename, 'wb') as f:
        f.write(uuid)

    key = fdnDCIC.FDN_Key(keypairs_file, "default")
    connection = fdnDCIC.FDN_Connection(key)
    response = fdnDCIC.new_FDN(connection, 'FileProcessed', newfile)
    print(response)
    s3 = boto3.resource('s3')
    s3.meta.client.upload_file(tmpfilename, bucket, upload_key)

    return newfile


def testrun_md5(keypairs_file, workflow_name='tibanna_pony', env='webdev'):
    """Creates a random file object with no md5sum/content_md5sum and run md5 workflow.
    It waits for 6 mintues till the workflow run finishes and checks the input file object
    has been updated.
    """
    bucket = "elasticbeanstalk-fourfront-" + env + "-wfoutput"
    newfile = post_random_file(bucket, keypairs_file)
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
        "output_bucket": bucket
    }
    resp = run_workflow(input_json, workflow=workflow_name)
    print(resp)

    # check result
    key = fdnDCIC.FDN_Key(keypairs_file, "default")
    connection = fdnDCIC.FDN_Connection(key)
    time.sleep(6*60)  # wait for 6 minutes
    filemeta = fdnDCIC.get_FDN(uuid, connection)
    content_md5sum = filemeta.get('content_md5sum')
    md5sum = filemeta.get('md5sum')
    if content_md5sum and md5sum:
        print(content_md5sum)
        print(md5sum)
    else:
        raise Exception('md5 step function run failed')
