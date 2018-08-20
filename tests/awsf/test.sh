#!/bin/bash

python awsf/aws_decode_run_json.py tests/awsf/bqLd8oa7Tdzq.run.json

## testing output upload / postrun json creation
python awsf/aws_upload_output_update_json.py tests/awsf/bqLd8oa7Tdzq.run.json tests/awsf/bqLd8oa7Tdzq.log.json tests/awsf/bqLd8oa7Tdzq.LOG tests/awsf/bqLd8oa7Tdzq.md5sum.txt tests/awsf/bqLd8oa7Tdzq.postrun.json.out

