#!/usr/bin/python
import json
import sys
import boto3
import os
import re
json_old = sys.argv[1]
execution_metadata = sys.argv[2]
logfile = sys.argv[3]
md5file = sys.argv[4]
json_new = sys.argv[5]

if len(sys.argv) > 6:
    language = sys.argv[6]
else:
    language = 'cwl-draft3'

source_directory = '/data1/out/'


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


def upload_to_s3(s3, source, bucket, target):
    if os.path.isdir(source):
        print("source " + source + " is a directory")
        source = source.rstrip('/')
        for root, dirs, files in os.walk(source):
            for f in files:
                source_f = os.path.join(root, f)
                if root == source:
                    target_f = os.path.join(target, f)
                else:
                    target_subdir = re.sub('^' + source + '/', '', root)
                    target_f = os.path.join(target, target_subdir, f)
                print("source_f=" + source_f)
                print("target_f=" + target_f)
                s3.upload_file(source_f, bucket, target_f)
            # for d in dirs:
            #     source_d = os.path.join(root, d)
            #     target_d = os.path.join(target, re.sub(source + '/', '', root), d)
            #     upload_to_s3(s3, source_d, bucket, target_d)
    else:
        print("source " + source + " is a not a directory")
        s3.upload_file(source, bucket, target)


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

if language == 'wdl':
    # read wdl output json file
    with open(execution_metadata, 'r') as json_out_f:
        wdl_output = json.load(json_out_f)
        old_dict['Job']['Output'].update({'Output files': {}})
        for argname, outfile in wdl_output['outputs'].items():
            if outfile:
                old_dict['Job']['Output']['Output files'].update({argname: {'path': outfile}})
elif language == 'snakemake':
    old_dict['Job']['Output'].update({'Output files': {}})
elif language == 'shell':
    old_dict['Job']['Output'].update({'Output files': {}})
else:
    # read cwl output json file
    with open(execution_metadata, 'r') as json_out_f:
        cwl_output = json.load(json_out_f)
        old_dict['Job']['Output'].update({'Output files': cwl_output})

output_meta = old_dict['Job']['Output']['Output files']

# fillig in md5
with open(md5file, 'r') as md5_f:
    md5dict = dict()
    for line in md5_f:
        a = line.split()
        path = a[1]
        md5sum = a[0]
        md5dict[path] = md5sum

for of, ofv in output_meta.items():
    if ofv['path'] in md5dict:
        ofv['md5sum'] = md5dict[ofv['path']]
    if 'secondaryFiles' in ofv:
        for sf in ofv['secondaryFiles']:
            if sf['path'] in md5dict:
                sf['md5sum'] = md5dict[sf['path']]

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
    if k.startswith('file://'):
        source = k.replace('file://', '')
        target = output_target[k]
        bucket = output_bucket  # default
        if target.startswith('s3://'):  # this allows using different output buckets
            output_path = re.sub('^s3://', '', target)
            bucket = output_path.split('/')[0]
            target = re.sub('^' + bucket + '/', '', output_path)
        try:
            print("uploading output file {} upload to {}".format(source, bucket + '/' + target))
            # s3.upload_file(source, bucket, target)
            upload_to_s3(s3, source, bucket, target)
        except Exception as e:
            raise Exception("output file {} upload to {} failed. %s".format(source, bucket + '/' + target) % e)


# legitimate CWL/WDL output targets
for k in output_meta:
    source = output_meta[k].get('path')
    source_name = source.replace(source_directory, '')
    bucket = output_bucket  # default
    if k in output_target:
        target = output_target[k]  # change file name to what's specified in output_target
        if target.startswith('s3://'):  # this allows using different output buckets
            output_path = re.sub('^s3://', '', target)
            bucket = output_path.split('/')[0]
            target = re.sub('^' + bucket + '/', '', output_path)
    else:
        target = source_name  # do not change file name
    print("uploading output file {} upload to {}".format(source, bucket + '/' + target))
    try:
        # s3.upload_file(source, bucket, target)
        upload_to_s3(s3, source, bucket, target)
    except Exception as e:
        raise Exception("output file {} upload to {} failed. %s".format(source, bucket + '/' + target) % e)
    try:
        output_meta[k]['target'] = target
    except Exception as e:
        raise Exception("cannot update target info to json %s" % e)

    if 'secondaryFiles' in output_meta[k]:
        n_assigned = 0
        n_target = len(secondary_output_target.get(k, []))
        for i, sf in enumerate(output_meta[k]['secondaryFiles']):
            source = sf.get('path')
            source_name = source.replace(source_directory, '')
            bucket = output_bucket  # default
            if k in secondary_output_target:
                if len(secondary_output_target[k]) == 1:  # one extra file
                    target = secondary_output_target[k][i]
                    n_assigned = n_assigned + 1
                else:
                    for targ in secondary_output_target[k]:
                        if targ[-3:] == source_name[-3:]:  # matching the last three letters
                            target = targ
                            n_assigned = n_assigned + 1
                            break
                if target.startswith('s3://'):  # this allows using different output buckets
                    output_path = re.sub('^s3://', '', target)
                    bucket = output_path.split('/')[0]
                    target = re.sub('^' + bucket + '/', '', output_path)
            else:
                target = source_name  # do not change file name
            try:
                print("uploading output file {} upload to {}".format(source, bucket + '/' + target))
                s3.upload_file(source, bucket, target)
            except Exception as e:
                raise Exception("output file {} upload to {} failed. %s".format(
                    source, bucket + '/' + target) % e)
            try:
                sf['target'] = target
            except Exception as e:
                raise Exception("cannot update target info to json %s" % e)
        if n_assigned != n_target:
            raise Exception("Error: Not all secondary output targets are uploaded!" +
                            "{} vs {}".format(n_assigned, n_target))

# add commands
old_dict['commands'] = parse_command(logfile)

# add file system info
old_dict['Job']['filesystem'] = os.environ.get('EBS_DEVICE', '')

# write to new json file
with open(json_new, 'w') as json_new_f:
    json.dump(old_dict, json_new_f, indent=4, sort_keys=True)
