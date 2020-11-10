import json
import os
import subprocess
import boto3
import re
from tibanna.awsem import AwsemRunJson
from tibanna.nnested_array import (
    run_on_nested_arrays2,
    flatten,
    create_dim
)


downloadlist_filename = "download_command_list.txt"
mountlist_filename = "mount_command_list.txt"
input_yml_filename = "inputs.yml"
env_filename = "env_command_list.txt"
INPUT_DIR = "/data1/input"  # data are downloaded to this directory
INPUT_MOUNT_DIR_PREFIX = "/data1/input-mounted-"  # data are mounted to this directory + bucket name


def decode_run_json(input_json_file):
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
    create_mount_command_list(mountlist_filename, runjson_input)

    # create an input yml file to be used on awsem
    if language == 'wdl':  # wdl
        create_input_for_wdl(input_yml_filename, runjson_input)
    elif language == 'snakemake':  # snakemake
        create_input_for_snakemake(input_yml_filename, runjson_input)
    else:  # cwl
        create_input_for_cwl(input_yml_filename, runjson_input)

    # create a file that defines environmental variables
    create_env_def_file(env_filename, runjson, language)


def create_mount_command_list(mountlist_filename, runjson_input):
    buckets_to_be_mounted = set()
    for category in ["Input_files_data", "Secondary_files_data"]:
        for inkey, v in getattr(runjson_input, category).items():
            if v.mount:
                buckets_to_be_mounted.add(v.dir_)
    with open(mountlist_filename, 'w') as f:
        for b in sorted(buckets_to_be_mounted):
            f.write("mkdir -p %s\n" % (INPUT_MOUNT_DIR_PREFIX + b))
            f.write("goofys-latest -f %s %s &\n" % (b, INPUT_MOUNT_DIR_PREFIX + b))


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
                    if len(flatten(v.rename)) == 0:
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
        if language == 'wdl':
            f_env.write("export WDL_URL={}\n".format(app.wdl_url))
            f_env.write("export MAIN_WDL={}\n".format(app.main_wdl))
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
        # other env variables
        f_env.write("export OUTBUCKET={}\n".format(runjson.Job.Output.output_bucket_directory))
        f_env.write("export PUBLIC_POSTRUN_JSON={}\n".format('1' if runjson.config.public_postrun_json else '0'))
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
    
    if language == 'wdl':
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
