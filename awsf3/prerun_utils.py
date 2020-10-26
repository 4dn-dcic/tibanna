import json
import os
import subprocess
import boto3
import re
from tibanna.awsem import AwsemRunJson


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
    create_download_command_list(downloadlist_filename, runjson_input, language)

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
    create_env_def_file(env_filename, runjson_input, language)


def create_mount_command_list(mountlist_filename, runjson_input):
    buckets_to_be_mounted = set()
    for category in ["Input_files_data", "Secondary_files_data"]:
        for inkey, v in getattr(runjson_input, category).items():
            if not v.mount:
                buckets_to_be_mounted.add(v.dir_)
    with open(mountlist_filename, 'w') as f:
        for b in buckets_to_be_mounted:
            f.write("mkdir -p %s\n" % (INPUT_MOUNT_DIR_PREFIX + b))
            f.write("goofys-latest -f %s %s &\n" % (b, INPUT_MOUNT_DIR_PREFIX + b))


def create_download_command_list(downloadlist_filename, runjson_input, language):
    """create a download command list file from the information in json"""
    with open(downloadlist_filename, 'w') as f:
        for category in ["Input_files_data", "Secondary_files_data"]:
            for inkey, v in getattr(runjson_input, category).items():
                if not v.mount:  # do not download if it will be mounted
                    continue
                if inkey.startswith('file://'):
                    if language not in ['shell', 'snakemake']:
                        raise Exception('input file has to be defined with argument name for CWL and WDL')
                    target = inkey.replace('file://', '')
                    if not target.startswith('/data1/'):
                        raise Exception('input target directory must be in /data1/')
                    if not target.startswith('/data1/' + language) and \
                        not target.startswith('/data1/input') and \
                        not target.startswith('/data1/out'):
                            raise Exception('input target directory must be in /data1/input, /data1/out or /data1/%s' % language)
                else:
                    target = ''
                    target_template = INPUT_DIR + "/%s"
                data_bucket = v.dir_
                profile_flag = "--profile " + v.profile if v.profile else ''
                path1 = v.path
                rename1 = v.rename
                if not rename1:
                    rename1 = path1
                if isinstance(path1, list):
                    for path2, rename2 in zip(path1, rename1):
                        if isinstance(path2, list):
                            for path3, rename3 in zip(path2, rename2):
                                if isinstance(path3, list):
                                    for data_file, rename4 in zip(path3, rename3):
                                        target = target_template % rename4
                                        add_download_cmd(data_bucket, data_file, target, profile_flag, f, v.unzip)
                                else:
                                    data_file = path3
                                    target = target_template % rename3
                                    add_download_cmd(data_bucket, data_file, target, profile_flag, f, v.unzip)
                        else:
                            data_file = path2
                            target = target_template % rename2
                            add_download_cmd(data_bucket, data_file, target, profile_flag, f, v.unzip)
                else:
                    data_file = path1
                    if not target:
                        target = target_template % rename1
                    add_download_cmd(data_bucket, data_file, target, profile_flag, f, v.unzip)


def add_download_cmd(data_bucket, data_file, target, profile_flag, f, unzip):
    if data_file:
        if data_file.endswith('/'):
            data_file = data_file.rstrip('/')
        cmd_template = "if [[ -z $(aws s3 ls s3://{0}/{1}/ {3}) ]]; then aws s3 cp s3://{0}/{1} {2} {3}; %s" + \
                       " else aws s3 cp --recursive s3://{0}/{1} {2} {3}; %s fi\n"
        cmd4 = ''
        cmd5 = ''
        if unzip == 'gz':
            cmd4 = "gunzip {2};"
            cmd5 = "for f in `find {2} -type f`; do if [[ $f =~ \.gz$ ]]; then gunzip $f; fi; done;"
        elif unzip == 'bz2':
            cmd4 = "bzip2 -d {2};"
            cmd5 = "for f in `find {2} -type f`; do if [[ $f =~ \.bz2$ ]]; then bzip2 -d $f; fi; done;"
        cmd = cmd_template % (cmd4, cmd5)
        f.write(cmd.format(data_bucket, data_file, target, profile_flag))


# create an input yml file for cwl-runner
def create_input_for_cwl(input_yml_filename, runjson_input):
    yml = runjson_input.as_dict_as_cwl_input()
    with open(input_yml_filename, 'w') as f_yml:
        json.dump(yml, f_yml, indent=4, sort_keys=True)


def create_input_for_wdl(input_yml_filename, runjson_input):
    yml = runjson_input.as_dict_as_wdl_input()
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
        if "Env" in runjson.Job.Input:
            for ev, val in runjson.Job.Input.Env.items():
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
