#!/usr/bin/python
import json
import os
import time
from .target import Target, SecondaryTargetList
from tibanna.awsem import AwsemPostRunJson, AwsemPostRunJsonOutput
    

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


def create_output_files_dict(language='cwl', execution_metadata=None, md5dict=None):
    """create a dictionary that contains 'path', 'secondaryFiles', 'md5sum' with argnames as keys.
    For snakemake and shell, returns an empty dictionary (execution_metadata not required).
    secondaryFiles is added only if the language is cwl.
    execution_metadata is a dictionary read from wdl/cwl execution log json file.
    md5dict is a dictionary with key=file path, value=md5sum (optional)."""
    if language in ['cwl', 'cwl_v1', 'cwl-draft3', 'wdl'] and not execution_metadata:
        raise Exception("execution_metadata is required for cwl/wdl.")
    out_meta = dict()
    if language == 'wdl':
        for argname, outfile in execution_metadata['outputs'].items():
            if outfile:
                out_meta[argname] = {'path': outfile}
    elif language == 'snakemake' or language == 'shell':
        out_meta = {}
    else:  # cwl, cwl_v1, cwl-draft3
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
    # read old json file and prepare postrunjson skeleton
    with open(json_old, 'r') as json_old_f:
        prj = AwsemPostRunJson(**json.load(json_old_f))

    # read md5 file
    md5dict = read_md5file(md5file)

    # read execution metadata file
    with open(execution_metadata_file, 'r') as f:
        execution_metadata = json.load(f)
    output_files = create_output_files_dict(language, execution_metadata, md5dict)

    # create output files for postrun json
    prj_out = prj.Job.Output
    prj_out.add_output_files(output_files)

    # parsing output_target and uploading output files to output target
    upload_to_output_target(prj_out)

    # add commands
    log_content = read_logfile_by_line(logfile)
    prj.add_commands(parse_commands(log_content))

    # add file system info
    prj.add_filesystem(os.environ.get('EBS_DEVICE', ''))

    # write to new json file
    with open(json_new, 'w') as json_new_f:
        json.dump(prj.as_dict(), json_new_f, indent=4, sort_keys=True)


def upload_to_output_target(prj_out):
    # parsing output_target and uploading output files to output target
    output_bucket = prj_out.output_bucket_directory
    output_argnames = prj_out.output_files.keys()
    output_target = prj_out.alt_output_target(output_argnames)

    for k in output_target:
        target = Target(output_bucket)

        # 'file://' output targets
        target.parse_custom_target(k, output_target[k])
        if target.is_valid:
            target.upload_to_s3()
        else:
            # legitimate CWL/WDL output targets
            target.parse_cwl_target(k, output_target.get(k, ''), prj_out.output_files)
            if target.is_valid:
                target.upload_to_s3()
                prj_out.output_files[k].add_target(target.dest)
    
                # upload secondary files
                secondary_output_files = prj_out.output_files[k].secondaryFiles
                if secondary_output_files:
                    stlist = SecondaryTargetList(output_bucket)
                    stlist.parse_target_values(prj_out.secondary_output_target.get(k, []))
                    stlist.reorder_by_source([sf.path for sf in secondary_output_files])
                    for st in stlist.secondary_targets:
                        st.upload_to_s3()
                    for i, sf in enumerate(secondary_output_files):
                        sf.add_target(stlist.secondary_targets[i].dest)
            else:
                raise Exception("Failed to upload to output target %s" % k)

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
