#!/bin/bash
set -o errexit

python awsf/aws_decode_run_json.py tests/awsf/bqLd8oa7Tdzq.run.json

## testing output upload / postrun json creation
# test for cwl
python awsf/aws_upload_output_update_json.py tests/awsf/bqLd8oa7Tdzq.run.json tests/awsf/bqLd8oa7Tdzq.log.json tests/awsf/bqLd8oa7Tdzq.LOG tests/awsf/bqLd8oa7Tdzq.md5sum.txt tests/awsf/bqLd8oa7Tdzq.postrun.json.out

# test for wdl
#python awsf/aws_upload_output_update_json.py tests/awsf/wdl/a3T0RlZ09WuR.run.json tests/awsf/wdl/a3T0RlZ09WuR.log.json tests/awsf/wdl/a3T0RlZ09WuR.log tests/awsf/wdl/a3T0RlZ09WuR.md5sum.txt tests/awsf/wdl/a3T0RlZ09WuR.postrun.json.out wdl


