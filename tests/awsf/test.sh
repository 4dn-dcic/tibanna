#!/bin/bash
#set -o errexit

# testing decoding run.json in awsem
# CWL
python awsf/aws_decode_run_json.py tests/awsf/bqLd8oa7Tdzq.run.json
python awsf/aws_decode_run_json.py tests/awsf/qD9zkkqAWjnE.run.json  # double-nested

# WDL
python awsf/aws_decode_run_json.py tests/awsf/wdl/pzn3Us98y21I.run.json   # nested
python awsf/aws_decode_run_json.py tests/awsf/wdl/uGeIte1giKxt.run.json  # double-nested

# shell
python awsf/aws_decode_run_json.py tests/awsf/bqLd8oa7Tdzr.run.json
if [[ $(grep COMMAND env_command_list.txt | wc -l) != "1" ]]
then
    exit 1
fi


## testing output upload / postrun json creation
# test for cwl
python awsf/aws_upload_output_update_json.py tests/awsf/bqLd8oa7Tdzq.run.json tests/awsf/bqLd8oa7Tdzq.log.json tests/awsf/bqLd8oa7Tdzq.LOG tests/awsf/bqLd8oa7Tdzq.md5sum.txt tests/awsf/bqLd8oa7Tdzq.postrun.json.out

# test for shell
python awsf/aws_upload_output_update_json.py tests/awsf/bqLd8oa7Tdzr.run.json - tests/awsf/bqLd8oa7Tdzr.log tests/awsf/bqLd8oa7Tdzq.md5sum.txt tests/awsf/bqLd8oa7Tdzr.postrun.json.out shell

# test for shell w/ multiple output
python awsf/aws_upload_output_update_json.py tests/awsf/bqLd8oa7Tdzs.run.json - tests/awsf/bqLd8oa7Tdzs.log tests/awsf/bqLd8oa7Tdzs.md5sum.txt tests/awsf/bqLd8oa7Tdzs.postrun.json.out shell

# test for wdl
# commented out since they will produce 'file not found error'. They work only if the files to upload exist.
#python awsf/aws_upload_output_update_json.py tests/awsf/wdl/a3T0RlZ09WuR.run.json tests/awsf/wdl/a3T0RlZ09WuR.log.json tests/awsf/wdl/a3T0RlZ09WuR.log tests/awsf/wdl/a3T0RlZ09WuR.md5sum.txt tests/awsf/wdl/a3T0RlZ09WuR.postrun.json.out wdl
#python awsf/aws_upload_output_update_json.py tests/awsf/wdl/a3T0RlZ09WuS.run.json tests/awsf/wdl/a3T0RlZ09WuS.log.json tests/awsf/wdl/a3T0RlZ09WuS.log tests/awsf/wdl/a3T0RlZ09WuS.md5sum.txt tests/awsf/wdl/a3T0RlZ09WuS.postrun.json.out wdl  # test for alt_cond_output_argnames

