import json
import os
import subprocess
import boto3
import re
import time
from tibanna.awsem import (
    AwsemRunJson,
    AwsemPostRunJson,
    AwsemPostRunJsonOutput
)
from tibanna.nnested_array import (
    run_on_nested_arrays2,
    flatten,
    create_dim
)
from .target import Target, SecondaryTargetList
from . import log


downloadlist_filename = "download_command_list.txt"
mountlist_filename = "mount_command_list.txt"
input_yml_filename = "inputs.yml"
env_filename = "env_command_list.txt"
INPUT_DIR = "/data1/input"  # data are downloaded to this directory
INPUT_MOUNT_DIR_PREFIX = "/data1/input-mounted-"  # data are mounted to this directory + bucket name


def decode_run_json(input_json_file, kms_key_id=None):
    """reads a run json file and creates three text files:
    download command list file (commands to download input files from s3)
    input yml file (for cwl/wdl/snakemake run)
    env list file (environment variables to be sourced)
    """
    # read json file
    with open(input_json_file, 'r') as f:
        runjson = AwsemRunJson(**json.load(f))
    runjson_input = runjson.Job.Input
    language = runjson.Job.App.language

    # create a download command list file from the information in json
    create_download_command_list(downloadlist_filename, runjson_input)

    # create a bucket-mounting command list file
    create_mount_command_list(mountlist_filename, runjson_input, kms_key_id=kms_key_id)

    # create an input yml file to be used on awsem
    if language in ['wdl', 'wdl_v1', 'wdl_draft2']:  # wdl
        create_input_for_wdl(input_yml_filename, runjson_input)
    elif language == 'snakemake':  # snakemake
        create_input_for_snakemake(input_yml_filename, runjson_input)
    else:  # cwl
        create_input_for_cwl(input_yml_filename, runjson_input)

    # create a file that defines environmental variables
    create_env_def_file(env_filename, runjson, language)


def create_mount_command_list(mountlist_filename, runjson_input,
                              kms_key_id=None):
    """ This function creates a mount point directory and starts goofys
        with some default arguments.
        Note that KMS key arguments are needed for the mount if encryption
        is enabled.
    """
    buckets_to_be_mounted = set()
    for category in ["Input_files_data", "Secondary_files_data"]:
        for inkey, v in getattr(runjson_input, category).items():
            if v.mount:
                buckets_to_be_mounted.add(v.dir_)
    with open(mountlist_filename, 'w') as f:
        for b in sorted(buckets_to_be_mounted):
            f.write("mkdir -p %s\n" % (INPUT_MOUNT_DIR_PREFIX + b))
            if kms_key_id:
                f.write("goofys --sse-kms %s -f %s %s &\n" % (kms_key_id, b, INPUT_MOUNT_DIR_PREFIX + b))
            else:
                f.write("goofys -f %s %s &\n" % (b, INPUT_MOUNT_DIR_PREFIX + b))


def create_download_command_list(downloadlist_filename, runjson_input):
    """create a download command list file from the information in json"""
    with open(downloadlist_filename, 'w') as f:
        for category in ["Input_files_data", "Secondary_files_data"]:
            for inkey, v in getattr(runjson_input, category).items():
                if v.mount:  # do not download if it will be mounted
                    continue
                if inkey.startswith('file://'):
                    target = inkey.replace('file://', '')
                    print("key %s will be downloaded to target %s" % (v.path, inkey))
                    run_on_nested_arrays2(v.path, target, add_download_cmd, data_bucket=v.dir_,
                                          profile=v.profile, f=f, unzip=v.unzip)
                else:
                    target_template = INPUT_DIR + "/%s"
                    if not v.rename or len(flatten(v.rename)) == 0:
                        rename = create_dim(v.path, empty=True)
                    else:
                        rename = v.rename
                    run_on_nested_arrays2(v.path, rename, add_download_cmd, data_bucket=v.dir_,
                                          profile=v.profile, f=f, unzip=v.unzip, target_template=target_template)


def add_download_cmd(data_file, rename, data_bucket, profile, f, unzip, target_template='%s'):
    if data_file:
        if not rename:
            rename = data_file
        target = target_template % rename
        cmd = create_download_cmd(data_bucket, data_file, target, profile, unzip)
        f.write(cmd + '\n')


def determine_key_type(bucket, key, profile):
    """Return values : 'File', 'Folder' or 'Does not exist'"""
    if profile:
        s3 = boto3.session(profile_name=profile).client('s3')
    else:
        s3 = boto3.client('s3')
    if not key:
        raise Exception("Cannot determine key type - no key is specified")
    if not bucket:
        raise Exception("Cannot determine key type - no bucket is specified")
    if key.endswith('/'):
        key = key.rstrip('/')
    res = s3.list_objects_v2(Bucket=bucket, Prefix=key + '/')
    if not 'KeyCount' in res:
        raise Exception("Cannot determine key type - no response from S3")
    if res['KeyCount'] == 0:
        res2 = s3.list_objects_v2(Bucket=bucket, Prefix=key)
        if not 'KeyCount' in res2:
            raise Exception("Cannot determine key type - no response from S3")
        elif res2['KeyCount'] == 0:
            return 'Does not exist'  # key does not exist
        # The file itself may be a prefix of another file (e.v. abc.vcf.gz vs abc.vcf.gz.tbi)
        # but it doesn't matter.
        else:
            return 'File'
    else:
        # data_file is a folder
        return 'Folder'


def create_download_cmd(data_bucket, data_file, target, profile, unzip=''):
    profile_flag = ' --profile ' + profile if profile else ''
    format_list = [data_bucket, data_file, target, profile_flag]
    key_type = determine_key_type(data_bucket, data_file, profile)
    if key_type == 'Does not exist':
        raise Exception("Cannot download file s3://%s/%s - file does not exist." % (data_bucket, data_file))
    elif key_type == 'File':
        download_cmd = 'aws s3 cp s3://{0}/{1} {2}{3}'.format(*format_list)
        if unzip == 'gz':
            unzip_cmd = 'gunzip {2}'
        elif unzip == 'bz2':
            unzip_cmd = 'bzip2 -d {2}'
        else:
            unzip_cmd = ''
        cmd = download_cmd + '; ' + unzip_cmd
        return cmd.format(*format_list)
    else: # key_type == 'Folder':
        download_cmd = 'aws s3 cp --recursive s3://{0}/{1} {2}{3}'.format(*format_list)
        if unzip == 'gz':
            unzip_cmd = 'for f in `find {2} -type f`; do if [[ $f =~ \\.gz$ ]]; then gunzip $f; fi; done;'
        elif unzip == 'bz2':
            unzip_cmd = 'for f in `find {2} -type f`; do if [[ $f =~ \\.bz2$ ]]; then bzip2 -d $f; fi; done;'
        else:
            unzip_cmd = ''
        cmd = download_cmd + '; ' + unzip_cmd
        return cmd.format(*format_list)


# create an input yml file for cwl-runner
def create_input_for_cwl(input_yml_filename, runjson_input):
    yml = runjson_input.as_dict_as_cwl_input(INPUT_DIR, INPUT_MOUNT_DIR_PREFIX)
    with open(input_yml_filename, 'w') as f_yml:
        json.dump(yml, f_yml, indent=4, sort_keys=True)


def create_input_for_wdl(input_yml_filename, runjson_input):
    yml = runjson_input.as_dict_as_wdl_input(INPUT_DIR, INPUT_MOUNT_DIR_PREFIX)
    with open(input_yml_filename, 'w') as f_yml:
        json.dump(yml, f_yml, indent=4, sort_keys=True)


def create_input_for_snakemake(input_yml_filename, runjson_input):
    pass  # for now assume no input yml


# create a file that defines environmental variables
def create_env_def_file(env_filename, runjson, language):
    # I have to use these variables after this script finishes running.
    # I didn't use os.environ + os.system('bash') because that would remove the other
    # env variables set before this script started running.
    app = runjson.Job.App
    with open(env_filename, 'w') as f_env:
        f_env.write("export LANGUAGE={}\n".format(app.language))
        if language in ['wdl', 'wdl_v1', 'wdl_draft2']:
            f_env.write("export WDL_URL={}\n".format(app.wdl_url))
            f_env.write("export MAIN_WDL={}\n".format(app.main_wdl))
            f_env.write("export WORKFLOW_ENGINE={}\n".format(app.workflow_engine))
            f_env.write("export RUN_ARGS={}\n".format(app.run_args))
            f_env.write("export WDL_FILES=\"{}\"\n".format(' '.join(app.other_wdl_files.split(','))))
        elif language == 'snakemake':
            f_env.write("export SNAKEMAKE_URL={}\n".format(app.snakemake_url))
            f_env.write("export MAIN_SNAKEMAKE={}\n".format(app.main_snakemake))
            f_env.write("export SNAKEMAKE_FILES=\"{}\"\n".format(' '.join(app.other_snakemake_files.split(','))))
            f_env.write("export COMMAND=\"{}\"\n".format(app.command.replace("\"", "\\\"")))
            f_env.write("export CONTAINER_IMAGE={}\n".format(app.container_image))
        elif language == 'shell':
            f_env.write("export COMMAND=\"{}\"\n".format(app.command.replace("\"", "\\\"")))
            f_env.write("export CONTAINER_IMAGE={}\n".format(app.container_image))
        else:  # cwl
            f_env.write("export CWL_URL={}\n".format(app.cwl_url))
            f_env.write("export MAIN_CWL={}\n".format(app.main_cwl))
            f_env.write("export CWL_FILES=\"{}\"\n".format(' '.join(app.other_cwl_files.split(','))))
            f_env.write("export RUN_ARGS={}\n".format(app.run_args))
        # other env variables
        env_preserv_str = ''
        docker_env_str = ''
        if runjson.Job.Input.Env:
            for ev, val in sorted(runjson.Job.Input.Env.items()):
                f_env.write("export {}={}\n".format(ev, val))
                env_preserv_str = env_preserv_str + "--preserve-environment " + ev + " "
                docker_env_str = docker_env_str + "-e " + ev + " "
        f_env.write("export PRESERVED_ENV_OPTION=\"{}\"\n".format(env_preserv_str))
        f_env.write("export DOCKER_ENV_OPTION=\"{}\"\n".format(docker_env_str))


def download_workflow():
    language = os.environ.get('LANGUAGE')
    if language == 'shell':
        return
    local_wfdir = os.environ.get('LOCAL_WFDIR')
    subprocess.call(['mkdir', '-p', local_wfdir])

    if language in ['wdl', 'wdl_v1', 'wdl_draft2']:
        main_wf = os.environ.get('MAIN_WDL', '')
        wf_files = os.environ.get('WDL_FILES', '')
        wf_url = os.environ.get('WDL_URL')
    elif language == 'snakemake':
        main_wf = os.environ.get('MAIN_SNAKEMAKE', '')
        wf_files = os.environ.get('SNAKEMAKE_FILES', '')
        wf_url = os.environ.get('SNAKEMAKE_URL')
    else:
        main_wf = os.environ.get('MAIN_CWL', '')
        wf_files = os.environ.get('CWL_FILES', '')
        wf_url = os.environ.get('CWL_URL')
    # turn into a list
    if not wf_files:
        wf_files = []
    elif ' ' in wf_files:
        wf_files = wf_files.split(' ')
    else:
        wf_files = [wf_files]
    wf_files.append(main_wf)
    wf_url = wf_url.rstrip('/')

    print("main workflow file: %s" % main_wf)
    print("workflow files: " + str(wf_files))

    s3 = boto3.client('s3')
    for wf_file in wf_files:
        target = "%s/%s" % (local_wfdir, wf_file)
        source = "%s/%s" % (wf_url, wf_file)

        if wf_url.startswith('http'):
            print("downloading via wget (public file)")
            subprocess.call(["wget", "-O" + target, source])
        elif wf_url.startswith('s3'):
            wf_loc = wf_url.replace('s3://', '')
            bucket_name = wf_loc.split('/')[0]
            if len(wf_loc.split('/')) > 1:
                subdirectory = wf_loc.replace(bucket_name + '/', '')
                key = subdirectory + '/' + wf_file
            else:
                key = wf_file
            print("downloading key %s from bucket %s to target %s" % (key, bucket_name, target))
            if '/' in target:
                targetdir = re.sub('[^/]+$', '', target)
                subprocess.call(["mkdir", "-p", targetdir])
            s3.download_file(Bucket=bucket_name, Key=key, Filename=target)


def read_md5file(md5file):
    with open(md5file, 'r') as md5_f:
        md5dict = dict()
        for line in md5_f:
            a = line.split()
            path = a[1]
            md5sum = a[0]
            md5dict[path] = md5sum
    return md5dict


def create_output_files_dict(language='cwl', execution_metadata=None, md5dict=None, strict=True):
    """create a dictionary that contains 'path', 'secondaryFiles', 'md5sum' with argnames as keys.
    For snakemake and shell, returns an empty dictionary (execution_metadata not required).
    secondaryFiles is added only if the language is cwl.
    execution_metadata is a dictionary read from wdl/cwl execution log json file.
    md5dict is a dictionary with key=file path, value=md5sum (optional).
    if strict is set False, then it does not check executio_metadata exists for cwl/wdl."""
    if language in ['cwl', 'cwl_v1', 'wdl', 'wdl_v1', 'wdl_draft2'] and not execution_metadata and strict:
        raise Exception("execution_metadata is required for cwl/wdl.")
    out_meta = dict()
    if language in ['wdl', 'wdl_v1', 'wdl_draft2']:
        for argname, outfile in execution_metadata['outputs'].items():
            if outfile:
                out_meta[argname] = {'path': outfile}
    elif language == 'snakemake' or language == 'shell':
        out_meta = {}
    else:  # cwl, cwl_v1
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


def read_postrun_json(jsonfile):
    # read old json file
    with open(jsonfile, 'r') as json_f:
        prj = AwsemPostRunJson(**json.load(json_f))
    return prj


def format_postrun_json(prj):
    return json.dumps(prj.as_dict(), indent=4, sort_keys=True)


def write_postrun_json(jsonfile, prj):
    with open(jsonfile, 'w') as f:
        f.write(format_postrun_json(prj))


def update_postrun_json_init(json_old, json_new):
    """Update postrun json with just instance ID, filesystem and availability zone"""
    # read old json file
    prj = read_postrun_json(json_old)

    # simply add instance ID, file system and availability zone
    prj.Job.instance_id = os.getenv('INSTANCE_ID')
    prj.Job.filesystem = os.getenv('EBS_DEVICE')
    prj.Job.instance_availablity_zone = os.getenv('INSTANCE_AVAILABILITY_ZONE')
    prj.Job.instance_type = os.getenv('INSTANCE_TYPE')

    # write to new json file
    write_postrun_json(json_new, prj)


def update_postrun_json_upload_output(json_old, execution_metadata_file, md5file, json_new,
                                      language='cwl_v1', strict=True, upload=True, endpoint_url=None):
    """Update postrun json with output files.
    if strict is set false, it does not check execution metadata is required for cwl/wdl."""
    # read old json file and prepare postrunjson skeleton
    prj = read_postrun_json(json_old)

    # read md5 file
    md5dict = read_md5file(md5file)

    # read execution metadata file
    if execution_metadata_file:
        with open(execution_metadata_file, 'r') as f:
            execution_metadata = json.load(f)
    else:
        execution_metadata = None
    output_files = create_output_files_dict(language, execution_metadata, md5dict, strict=strict)

    # create output files for postrun json
    prj.Job.Output.add_output_files(output_files)

    # upload output to S3 (this also updates postrun json)
    if upload:
        upload_output(prj, endpoint_url=endpoint_url)

    # write to new json file
    write_postrun_json(json_new, prj)


def upload_output(prj, endpoint_url=None):
    # parsing output_target and uploading output files to output target
    upload_to_output_target(prj.Job.Output, prj.config.encrypt_s3_upload,
                            kms_key_id=prj.config.kms_key_id, endpoint_url=endpoint_url)


def upload_to_output_target(prj_out, encrypt_s3_upload=False, kms_key_id=None, endpoint_url=None):
    # parsing output_target and uploading output files to output target
    output_bucket = prj_out.output_bucket_directory
    output_argnames = prj_out.output_files.keys()
    output_target = prj_out.alt_output_target(output_argnames)

    for k in output_target:
        target = Target(output_bucket)

        # 'file://' output targets
        if target.is_custom_target(k):
            print("processing custom (path-based) target %s" % k)
            target.parse_custom_target(k, output_target[k])
            if target.is_valid:
                print("Target is valid. Uploading..")
                target.upload_to_s3(encrypt_s3_upload=encrypt_s3_upload, endpoint_url=endpoint_url)
            else:
                raise Exception("Invalid target %s -> %s: failed to upload" % k, output_target[k])
        else:
            # legitimate CWL/WDL output targets
            print("processing argument-based target %s" % k)
            target.parse_cwl_target(k, output_target.get(k, ''), prj_out.output_files)
            if target.is_valid:
                print("Target is valid. Uploading..")
                target.upload_to_s3(encrypt_s3_upload=encrypt_s3_upload,
                                    kms_key_id=kms_key_id, endpoint_url=endpoint_url)
                prj_out.output_files[k].add_target(target.dest)

                # upload secondary files
                secondary_output_files = prj_out.output_files[k].secondaryFiles
                if secondary_output_files:
                    stlist = SecondaryTargetList(output_bucket)
                    stlist.parse_target_values(prj_out.secondary_output_target.get(k, []))
                    stlist.reorder_by_source([sf.path for sf in secondary_output_files])
                    for st in stlist.secondary_targets:
                        st.upload_to_s3(encrypt_s3_upload=encrypt_s3_upload,
                                        kms_key_id=kms_key_id, endpoint_url=endpoint_url)
                    for i, sf in enumerate(secondary_output_files):
                        sf.add_target(stlist.secondary_targets[i].dest)
            else:
                raise Exception("Failed to upload to output target %s" % k)


def save_total_sizes():
    os.environ['INPUTSIZE'] = subprocess.getoutput('du -csh /data1/input| tail -1 | cut -f1')
    os.environ['TEMPSIZE'] = subprocess.getoutput('du -csh /data1/tmp*| tail -1 | cut -f1')
    os.environ['OUTPUTSIZE'] = subprocess.getoutput('du -csh /data1/out| tail -1 | cut -f1')


def update_postrun_json_final(json_old, json_new, logfile=None):
    """Update postrun json with status, time stamps, parsed commands,
    input/tmp/output sizes"""
    prj = read_postrun_json(json_old)

    postrun_json_final(prj, logfile=logfile)

    # write to new json file
    write_postrun_json(json_new, prj)


def postrun_json_final(prj, logfile=None):
    # add commands
    if logfile:
        print("parsing commands from log file...")
        log_content = log.read_logfile_by_line(logfile)
        prj.update(commands=log.parse_commands(log_content))
    # add end time, status, instance_id
    prj_job = prj.Job
    prj_job.update(end_time=time.strftime("%Y%m%d-%H:%M:%S-%Z"))
    prj_job.update(status=os.getenv('JOB_STATUS'))
    prj_job.update(total_input_size=os.getenv('INPUTSIZE'))
    prj_job.update(total_tmp_size=os.getenv('TEMPSIZE'))
    prj_job.update(total_output_size=os.getenv('OUTPUTSIZE'))


def upload_postrun_json(jsonfile):
    prj = read_postrun_json(jsonfile)
    bucket = prj.Job.Log.log_bucket_directory
    dest = prj.Job.JOBID + '.postrun.json'
    if '/' in bucket:
        bucket_dirs = bucket.split('/')
        bucket = bucket_dirs.pop(0)
        prefix = '/'.join(bucket_dirs)
        dest = prefix + '/' + dest
    if prj.config.public_postrun_json:
        acl = 'public-read'
    else:
        acl = 'private'
    s3 = boto3.client('s3')
    upload_arg = {
        "Body": format_postrun_json(prj).encode('utf-8'),
        "Bucket": bucket,
        "Key": dest,
        "ACL": acl
    }
    if prj.config.encrypt_s3_upload:
        upload_arg.update({"ServerSideEncryption": "aws:kms"})
        if prj.config.kms_key_id:
            upload_arg['SSEKMSKeyId'] = prj.config.kms_key_id
    s3.put_object(**upload_arg)
