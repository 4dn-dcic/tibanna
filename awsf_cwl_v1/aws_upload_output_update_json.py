#!/usr/bin/python
import json
import sys
import boto3
json_old = sys.argv[1]
cwl_json_out = sys.argv[2]
logfile = sys.argv[3]
md5file = sys.argv[4]
json_new = sys.argv[5]

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


# read old json file
with open(json_old, 'r') as json_old_f:
    old_dict = json.load(json_old_f)
    output_target = old_dict.get('Job').get('Output').get('output_target')
    output_bucket = old_dict.get('Job').get('Output').get('output_bucket_directory')
    secondary_output_target = old_dict.get('Job').get('Output').get('secondary_output_target')

# read cwl output json file
with open(cwl_json_out, 'r') as json_out_f:
    cwl_output = json.load(json_out_f)
    old_dict['Job']['Output'].update({'Output files': cwl_output})

# fillig in md5
with open(md5file, 'r') as md5_f:
    md5dict = dict()
    for line in md5_f:
        a = line.split()
        path = a[1]
        md5sum = a[0]
        md5dict[path] = md5sum

for of, ofv in old_dict['Job']['Output']['Output files'].iteritems():
    if ofv['path'] in md5dict:
        ofv['md5sum'] = md5dict[ofv['path']]
    if 'secondaryFiles' in ofv:
        for sf in ofv['secondaryFiles']:
            if sf['path'] in md5dict:
                ofv['md5sum'] = md5dict[sf['path']]

# sanity check for output target, this skips secondary files
# - we assume secondary files are not explicitly specified in output_target.
for k in output_target:
    if k not in cwl_output:
        raise Exception("output target key {} doesn't exist in cwl-runner output".format(k))

# upload output file
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
        raise Exception("output file {} upload to {} failed. %s".format(source, output_bucket + '/' + target) % e)
    try:
        cwl_output[k]['target'] = target
    except Exception as e:
        raise Exception("cannot update target info to json %s" % e)

    if 'secondaryFiles' in cwl_output[k]:
        n_assigned = 0
        n_target = sum([len(v) for u, v in secondary_output_target.items()])
        for i, sf in enumerate(cwl_output[k]['secondaryFiles']):
            source = sf.get('path')
            source_name = source.replace(source_directory, '')
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
            else:
                target = source_name  # do not change file name
            try:
                print("uploading output file {} upload to {}".format(source, output_bucket + '/' + target))
                s3.upload_file(source, output_bucket, target)
            except Exception as e:
                raise Exception("output file {} upload to {} failed. %s".format(
                    source, output_bucket + '/' + target) % e)
            try:
                sf['target'] = target
            except Exception as e:
                raise Exception("cannot update target info to json %s" % e)
        if n_assigned != n_target:
            raise Exception("Error: Not all secondary output targets are uploaded!" +
                            "{} vs {}".format(n_assigned, n_target))

# add commands
old_dict['commands'] = parse_command(logfile)

# write to new json file
with open(json_new, 'w') as json_new_f:
    json.dump(old_dict, json_new_f, indent=4, sort_keys=True)
