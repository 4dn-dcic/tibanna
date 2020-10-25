#!/usr/bin/python
import json
import os
import time
from .target import Target, SecondaryTargetList
    

def read_logfile_by_line(logfile):
    """generator function that yields the log file content line by line"""
    with open(logfile, 'r') as f:
        for line in f:
            yield line
    yield None


def parse_commands(log_content):
    """
    parse cwl commands from the line-by-line generator of log file content and
    returns the commands as a list of command line lists, each corresponding to a step run.
    """
    command_list = []
    command = []
    in_command = False
    line = next(log_content)
    while(line):
        line = line.strip('\n')
        if line.startswith('[job') and line.endswith('docker \\'):
            line = 'docker \\'  # remove the other stuff
            in_command = True
        if in_command:
            command.append(line.strip('\\').rstrip(' '))
            if not line.endswith('\\'):
                in_command = False
                command_list.append(command)
                command = []
        line = next(log_content)
    return(command_list)


def read_md5file(md5file):
    with open(md5file, 'r') as md5_f:
        md5dict = dict()
        for line in md5_f:
            a = line.split()
            path = a[1]
            md5sum = a[0]
            md5dict[path] = md5sum
    return md5dict


def create_out_meta(language='cwl', execution_metadata=None, md5dict=None):
    """create a dictionary that contains 'path', 'secondaryFiles', 'md5sum' with argnames as keys.
    For snakemake and shell, returns an empty dictionary (execution_metadata not required).
    secondaryFiles is added only if the language is cwl.
    execution_metadata is a dictionary read from wdl/cwl execution log json file.
    md5dict is a dictionary with key=file path, value=md5sum (optional)."""
    if language in ['cwl', 'wdl'] and not execution_metadata:
        raise Exception("execution_metadata is required for cwl/wdl.")
    out_meta = dict()
    if language == 'wdl':
        for argname, outfile in execution_metadata['outputs'].items():
            if outfile:
                out_meta[argname] = {'path': outfile}
    elif language == 'snakemake' or language == 'shell':
        out_meta = {}
    else:
        # read cwl output json file
        out_meta = execution_metadata

    # add md5
    if not md5dict:
        md5dict = {}
    for of, ofv in out_meta.items():
        if ofv['path'] in md5dict:
            ofv['md5sum'] = md5dict[ofv['path']]
        if 'secondaryFiles' in ofv:
            for sf in ofv['secondaryFiles']:
                if sf['path'] in md5dict:
                    sf['md5sum'] = md5dict[sf['path']]

    return out_meta


def upload_output_update_json(json_old, execution_metadata_file, logfile, md5file, json_new, language='cwl-draft3'):

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
    md5dict = read_md5file(md5file)

    # output meta
    with open(execution_metadata_file, 'r') as f:
        execution_metadata = json.load(f)
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

    # 'file://' output targets
    for k in output_target:
        target = Target(output_bucket)
        target.parse_custom_target(k, output_target[k])
        target.upload_to_s3()

    # legitimate CWL/WDL output targets
    for k in output_meta:
        target = Target(output_bucket)
        target.parse_cwl_target(k, output_target.get(k, ''), output_meta)
        target.upload_to_s3()
        try:
            output_meta[k]['target'] = target.dest
        except Exception as e:
            raise Exception("cannot update target info to json %s" % e)
        # upload secondary files
        if 'secondaryFiles' in output_meta[k]:
            stlist = SecondaryTargetList(output_bucket)
            stlist.parse_target_values(secondary_output_target.get(k, []))
            stlist.reorder_by_source([sf.get('path') for sf in output_meta[k]['secondaryFiles']])
            for st in stlist.as_dict():
                st.upload_to_s3()
            try:
                for i, sf in enumerate(output_meta[k]['secondaryFiles']):
                    sf['target'] = stlist[i].dest
            except Exception as e:
                raise Exception("cannot update target info to json %s" % e)

    # add commands
    log_content = read_logfile_by_line(logfile)
    old_dict['commands'] = parse_commands(log_content)

    # add file system info
    old_dict['Job']['filesystem'] = os.environ.get('EBS_DEVICE', '')

    # write to new json file
    with open(json_new, 'w') as json_new_f:
        json.dump(old_dict, json_new_f, indent=4, sort_keys=True)


def update_postrun_json(json_old, json_new):
    # read old json file
    with open(json_old, 'r') as json_old_f:
        Dict = json.load(json_old_f)
    update_postrun_json_job_content(Dict['Job'])
    # write to new json file
    with open(json_new, 'w') as json_new_f:
        json.dump(Dict, json_new_f, indent=4, sort_keys=True)
    

def update_postrun_json_job_content(dict_job):    
    # add end time, status, instance_id
    dict_job['end_time'] = time.strftime("%Y%m%d-%H:%M:%S-%Z")
    dict_job['status'] = os.getenv('JOB_STATUS')
    dict_job['instance_id'] = os.getenv('INSTANCE_ID')
    dict_job['total_input_size'] = os.getenv('INPUTSIZE')
    dict_job['total_tmp_size'] = os.getenv('TEMPSIZE')
    dict_job['total_output_size'] = os.getenv('OUTPUTSIZE')
