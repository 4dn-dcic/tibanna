#!/usr/bin/python
import json
import sys
import boto3
import os
import re
from .target import Target, SecondaryTargetList, create_out_meta


json_old = sys.argv[1]
execution_metadata = sys.argv[2]
logfile = sys.argv[3]
md5file = sys.argv[4]
json_new = sys.argv[5]

if len(sys.argv) > 6:
    language = sys.argv[6]
else:
    language = 'cwl-draft3'


def parse_command(logfile):
    """
    parse commands from the log file and returns the commands as a list
    of command line lists, each corresponding to a step run.
    """
    command_list = []
    command = []
    in_command = False
    with open(logfile, 'r') as f:
        for line in f:
            line = line.strip('\n')
            if line.startswith('[job') and line.endswith('docker \\'):
                in_command = True
            if in_command:
                command.append(line.strip('\\'))
                if not line.endswith('\\'):
                    in_command = False
                    command_list.append(command)
                    command = []
    return(command_list)


def upload_to_s3(s3, source, bucket, dest, unzip=False):
    if os.path.isdir(source):
        print("source " + source + " is a directory")
        source = source.rstrip('/')
        for root, dirs, files in os.walk(source):
            for f in files:
                source_f = os.path.join(root, f)
                if root == source:
                    dest_f = os.path.join(dest, f)
                else:
                    dest_subdir = re.sub('^' + source + '/', '', root)
                    dest_f = os.path.join(dest, dest_subdir, f)
                print("source_f=" + source_f)
                print("dest_f=" + dest_f)
                s3.upload_file(source_f, bucket, dest_f)
    else:
        print("source " + source + " is a not a directory")
        s3.upload_file(source, bucket, dest)


# read old json file
with open(json_old, 'r') as json_old_f:
    old_dict = json.load(json_old_f)
    output_target = old_dict.get('Job').get('Output').get('output_target')
    alt_output_argnames = old_dict.get('Job').get('Output').get('alt_cond_output_argnames')
    output_bucket = old_dict.get('Job').get('Output').get('output_bucket_directory')
    secondary_output_target = old_dict.get('Job').get('Output').get('secondary_output_target')
    for u, v in secondary_output_target.items():
        if not isinstance(v, list):
            secondary_output_target[u] = [v]


# fillig in md5
with open(md5file, 'r') as md5_f:
    md5dict = dict()
    for line in md5_f:
        a = line.split()
        path = a[1]
        md5sum = a[0]
        md5dict[path] = md5sum


output_meta = create_out_meta(language, execution_metadata, md5dict)
old_dict['Job']['Output']['Output files'] = output_meta


# sanity check for output target, this skips secondary files
# in case conditional alternative output targets exist, replace the output target key with
# the alternative name
# We don't need to do the same for secondary files because
# conditional alternative names only occur in WDL which does not support secondary files
replace_list = []
for k in output_target:
    if k.startswith('file://'):
        continue
    if k not in output_meta:
        if k in alt_output_argnames:
            key_exists = False  # initialize
            for k_alt in alt_output_argnames[k]:
                if k_alt in output_meta and output_meta[k_alt]['path']:
                    key_exists = True
                    replace_list.append((k, k_alt))
            if not key_exists:
                raise Exception("output target key {} doesn't exist in cwl-runner output".format(k))
        else:
            raise Exception("output target key {} doesn't exist in cwl-runner output".format(k))
for k, k_alt in replace_list:
    output_target[k_alt] = output_target[k]
    del output_target[k]

s3 = boto3.client('s3')

# 'file://' output targets
for k in output_target:
    target = Target(output_bucket)
    target.parse_custom_target(k, output_target[k])
    if target.is_valid:
        try:
            print("uploading output file {} upload to {}".format(source, bucket + '/' + target))
            upload_to_s3(s3, **target.as_dict())
        except Exception as e:
            raise Exception("output file {} upload to {} failed. %s".format(source, bucket + '/' + target) % e)

# legitimate CWL/WDL output targets
for k in output_meta:
    target = Target(output_bucket)
    target.parse_cwl_target(k, output_target.get(k, ''), output_meta)
    print("uploading output file {} upload to {}".format(source, bucket + '/' + target))
    try:
        upload_to_s3(s3, **target.as_dict())
    except Exception as e:
        raise Exception("output file {} upload to {} failed. %s".format(source, bucket + '/' + target) % e)
    try:
        output_meta[k]['target'] = target.dest
    except Exception as e:
        raise Exception("cannot update target info to json %s" % e)
    if 'secondaryFiles' in output_meta[k]:
        stlist = SecondaryTargetList(output_bucket)
        stlist.parse_target_values(secondary_output_target.get(k, []))
        stlist.reorder_by_source([sf.get('path') for sf in output_meta[k]['secondaryFiles']])
        for st in stlist.as_dict():
            s3.upload_file(**st)
        try:
            for sf, st in zip(output_meta[k]['secondaryFiles'], stlist):
                sf['target'] = st.dest
        except Exception as e:
            raise Exception("cannot update target info to json %s" % e)

# add commands
old_dict['commands'] = parse_command(logfile)

# add file system info
old_dict['Job']['filesystem'] = os.environ.get('EBS_DEVICE', '')

# write to new json file
with open(json_new, 'w') as json_new_f:
    json.dump(old_dict, json_new_f, indent=4, sort_keys=True)
