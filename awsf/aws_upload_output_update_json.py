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


class Target(object):
    def __init__(self):
        self.source = ''
        self.bucket = output_bucket
        self.dest = ''
        self.unzip = False

    @property
    def source_name(self):
        self.source.replace(source_directory, '')

    def is_valid(self):
        if self.source and self.dest and self.bucket:
            return True
        else:
            return False

    def parse_custom_target(self, target_key, target_value):
        """takes a key-value pair from output_target, parses the content.
        This function only handles custom cases where the key starts with file://
        (not valid CWL/WDL targets)"""
        if target_key.startswith('file://'):
            self.source = target_key.replace('file://', '')
            if not target_value:
                raise Exception("output_target missing for target %s" % target_key)
            self.parse_target_value(target_value)

    def parse_cwl_target(self, target_key, target_value, output_meta):
        """takes a key-value pair from output_target, parses the content.
        output_meta is a dictionary that contains {<argname>: {'path': <outfile_path_on_awsem>}}"""
        self.source = output_meta[target_key].get('path')
        if target_value:
            self.parse_target_value(target_value)
        else:
            self.dest = self.source_name  # do not change file name

    def parse_target_value(self, target_value):
        """target value can be a dictionary with following keys: object_key, bucket_name, object_prefix, unzip.
        or it can be a string that refers to the object_key or in the format of s3://<bucket_name>/<object_key>.
        This function changes attributes bucket, dest, unzip."""
        if isinstance(target_value, dict):
            if 'unzip' in target_value:
                self.unzip = True
            if 'bucket_name' in target_value:  # this allows using different output buckets
                self.bucket = target_value['bucket_name']
            if 'object_prefix' in target_value:
                if 'object_key' in target_value:
                    raise Exception("Specify either object_key or object_prefix, but not both in output_target")
                if not target_value['object_prefix'].endswith('/'):
                    target_value['object_prefix'] += '/'
                self.dest = target_value['object_prefix']
            if 'object_key' in target_value:
                self.dest = target_value['object_key']
        elif isinstance(target_value, str):
            if target_value.startswith('s3://'):  # this allows using different output buckets
                output_path = re.sub('^s3://', '', target_value)
                self.bucket = output_path.split('/')[0]
                self.dest = re.sub('^' + bucket + '/', '', output_path)
            else:
                self.dest = target_value  # change file name to what's specified in output_target

    def as_dict(self):
        return self.__dict__


class SecondaryTarget(Target):
    def is_matched(self, source_path):
        if not self.dest:
            raise Exception("first calculate dest (destination) to check matching.")
        # check the last three letters between dest and source_path
        if self.dest[-3:] == source_path[-3:]:
            return True
        else:
            return False

    def parse_custom_target(self, target_key, target_value):
        raise Exception("Function disabled")

    def parse_cwl_target(self, target_key, target_value, output_meta):
        raise Exception("Function disabled")


class SecondaryTargetList(object):
    def __init__(self):
        self.n = 0  # size of the list (i.e. number of secondary targets)
        self.secondary_targets = []  # list of SecondaryTarget objects

    def parse_target_values(self, target_values):
        self.n = len(target_values)  # size of the list (i.e. number of secondary targets)
        self.secondary_targets = [SecondaryTarget() for i in range(self.n)]
        for st, tv in zip(self.secondary_targets, target_values):
            st.parse_target_value(tv)

    def reorder_by_source(self, source_paths):
        if len(source_paths) < self.n:
            raise Exception("Not enough source_paths for secondary targets " +
                            "(%d vs %d)" % (len(source_paths), self.n))
        n_assigned = 0
        reordered_secondary_targets = []
        for sp in source_paths:
            for st in self.secondary_targets:
                if st.is_matched(sp):
                    st.source = sp
                    reordered_secondary_targets.append(st)
                    n_assigned += 1
                    break

            # if no matching target is defined, use the source name
            additional_st = SecondaryTarget()
            additional_st.source = sp
            additional_st.dest = additional_st.source_name
            reordered_secondary_targets.append(additiona_st)
            n_assigned += 1
            self.n += 1

        if n_assigned != self.n:
            raise Exception("Error: Not all secondary output targets are being uploaded!" +
                            "{} vs {}".format(n_assigned, self.n))
        self.secondary_targets = reordered_secondary_targets

    def as_dict(self):
        return [st.as_dict() for st in self.secondary_targets]


def create_out_meta(language='cwl', execution_metadata, md5dict=None):
    """create a dictionary that contains 'path', 'secondaryFiles', 'md5sum' with argnames as keys.
    For snakemake and shell, returns an empty dictionary.
    secondaryFiles is added only if the language is cwl.
    md5dict is a dictionary with key=file path, value=md5sum (optional)"""
    out_meta = dict()
    if language == 'wdl':
        # read wdl output json file
        with open(execution_metadata, 'r') as json_out_f:
            wdl_output = json.load(json_out_f)
        for argname, outfile in wdl_output['outputs'].iteritems():
            if outfile:
                out_meta[argname] = {'path': outfile}
    elif language == 'snakemake' or language == 'shell':
        out_meta = {}
    else:
        # read cwl output json file
        with open(execution_metadata, 'r') as json_out_f:
            out_meta = json.load(json_out_f)

    # add md5
    if not md5dict:
        md5dict = {}
    for of, ofv in out_meta.iteritems():
        if ofv['path'] in md5dict:
            ofv['md5sum'] = md5dict[ofv['path']]
        if 'secondaryFiles' in ofv:
            for sf in ofv['secondaryFiles']:
                if sf['path'] in md5dict:
                    sf['md5sum'] = md5dict[sf['path']]

    return out_meta


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
    target = Target()
    target.parse_custom_target(k, output_target[k])
    if target.is_valid:
        try:
            print("uploading output file {} upload to {}".format(source, bucket + '/' + target))
            upload_to_s3(s3, **target.as_dict())
        except Exception as e:
            raise Exception("output file {} upload to {} failed. %s".format(source, bucket + '/' + target) % e)

# legitimate CWL/WDL output targets
for k in output_meta:
    target = Target()
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
        stlist = SecondaryTargetList()
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
