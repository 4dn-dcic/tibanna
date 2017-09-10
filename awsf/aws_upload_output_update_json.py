#!/usr/bin/python
import json
import sys
import os
import time
import boto3
json_old=sys.argv[1]
json_out=sys.argv[2]
json_new=sys.argv[3]

source_directory = '/data1/out/'
 
## read old json file
with open(json_old, 'r') as json_old_f:
    old_dict = json.load(json_old_f)
    output_target = old_dict.get('Job').get('Output').get('output_target')
    output_bucket = old_dict.get('Job').get('Output').get('output_bucket_directory')
    secondary_output_target = old_dict.get('Job').get('Output').get('secondary_output_target')

## read cwl output json file
with open(json_out, 'r') as json_out_f:
    cwl_output = json.load(json_out_f)
    old_dict['Job']['Output'].update({'Output files': cwl_output})

## sanity check for output target, this skips secondary files - we assume secondary files are not explicitly specified in output_target.
for k in output_target:
    if k not in cwl_output:
        raise Exception("output target key {} doesn't exist in cwl-runner output".format(k))

## upload output file
s3 = boto3.client('s3')
for k in cwl_output:
    source = cwl_output[k].get('path')
    source_name = source.replace(source_directory, '')
    if k in output_target:
        target = output_target[k]  # change file name to what's specified in output_target
    else:
        target = source_name  # do not change file name
    try:
        print("uploading output file {} upload to {}".format(source, output_bucket + '/' + target))
        s3.upload_file(source, output_bucket, target)
    except Exception as e:
        raise Exception("output file {} upload to {} failed. %s".format(source, output_bucket + '/' + target) % e )
    try:
        cwl_output[k]['target'] = target
    except Exception as e:
        raise Exception("cannot update target info to json %s" % e)

    if 'secondaryFiles' in cwl_output[k]:
        sf = cwl_output[k]['secondaryFiles'][0]
        for kk in sf:
            source = sf[kk].get('path')
            source_name = source.replace(source_directory, '')
            if k in secondary_output_target:
                target = secondary_output_target[k]  # change file name to what's specified in secondary_output_target
            else:
                target = source_name  # do not change file name
            try:
                print("uploading output file {} upload to {}".format(source, output_bucket + '/' + target))
                s3.upload_file(source, output_bucket, target)
            except Exception as e:
                raise Exception("output file {} upload to {} failed. %s".format(source, output_bucket + '/' + target) % e )
            try:
                sf[kk]['target'] = target
            except Exception as e:
                raise Exception("cannot update target info to json %s" % e)

## write to new json file
with open(json_new, 'w') as json_new_f:
     json.dump(old_dict, json_new_f, indent=4, sort_keys=True)
