#!/usr/bin/python
import json
import sys
import re

downloadlist_filename = "download_command_list.txt"
mountlist_filename = "mount_command_list.txt"
input_yml_filename = "inputs.yml"
env_filename = "env_command_list.txt"
INPUT_DIR = "/data1/input"  # data are downloaded to this directory
INPUT_MOUNT_DIR_PREFIX = "/data1/input-mounted-"  # data are mounted to this directory + bucket name


def main():
    """reads a run json file and creates three text files:
    download command list file (commands to download input files from s3)
    input yml file (for cwl/wdl/snakemake run)
    env list file (environment variables to be sourced)
    """
    # read json file
    with open(sys.argv[1], 'r') as json_file:
        d = json.load(json_file)
    d_input = d["Job"]["Input"]
    language = d["Job"]["App"]["language"]

    # create a download command list file from the information in json
    create_download_command_list(downloadlist_filename, d_input, language)

    # create a bucket-mounting command list file
    create_mount_command_list(mountlist_filename, d_input)

    # create an input yml file to be used on awsem
    if language == 'wdl':  # wdl
        create_input_for_wdl(input_yml_filename, d_input)
    elif language == 'snakemake':  # snakemake
        create_input_for_snakemake(input_yml_filename, d_input)
    else:  # cwl
        create_input_for_cwl(input_yml_filename, d_input)

    # create a file that defines environmental variables
    create_env_def_file(env_filename, d, language)


def create_mount_command_list(mountlist_filename, d_input):
    buckets_to_be_mounted = dict()
    for category in ["Input_files_data", "Secondary_files_data"]:
        for inkey, v in d_input[category].iteritems():
            if v.get("mount", False): 
                buckets_to_be_mounted[v['dir']] = 1
    with open(mountlist_filename, 'w') as f:
        for b in buckets_to_be_mounted:
            f.write("mkdir -p %s\n" % (INPUT_MOUNT_DIR_PREFIX + b))
            f.write("$GOOFYS_COMMAND %s %s\n" % (b, INPUT_MOUNT_DIR_PREFIX + b))


def create_download_command_list(downloadlist_filename, d_input, language):
    """create a download command list file from the information in json"""
    with open(downloadlist_filename, 'w') as f:
        for category in ["Input_files_data", "Secondary_files_data"]:
            for inkey, v in d_input[category].iteritems():
                if v.get("mount", False):  # do not download if it will be mounted
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
                data_bucket = v["dir"]
                profile = v.get("profile", '')
                profile_flag = "--profile " + profile if profile else ''
                path1 = v["path"]
                rename1 = v.get("rename", None)
                unzip = v.get("unzip", None)
                if not rename1:
                    rename1 = path1
                if isinstance(path1, list):
                    for path2, rename2 in zip(path1, rename1):
                        if isinstance(path2, list):
                            for path3, rename3 in zip(path2, rename2):
                                if isinstance(path3, list):
                                    for data_file, rename4 in zip(path3, rename3):
                                        target = target_template % rename4
                                        add_download_cmd(data_bucket, data_file, target, profile_flag, f, unzip)
                                else:
                                    data_file = path3
                                    target = target_template % rename3
                                    add_download_cmd(data_bucket, data_file, target, profile_flag, f, unzip)
                        else:
                            data_file = path2
                            target = target_template % rename2
                            add_download_cmd(data_bucket, data_file, target, profile_flag, f, unzip)
                else:
                    data_file = path1
                    if not target:
                        target = target_template % rename1
                    add_download_cmd(data_bucket, data_file, target, profile_flag, f, unzip)


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


def file2cwlfile(filename, dir, unzip):
    if unzip:
        filename = re.match('(.+)\.{0}$'.format(unzip), filename).group(1)
    return {"class": 'File', "path": dir + '/' + filename}


def file2wdlfile(filename, dir, unzip):
    if unzip:
        filename = re.match('(.+)\.{0}$'.format(unzip), filename).group(1)
    return dir + '/' + filename


# create an input yml file for cwl-runner
def create_input_for_cwl(input_yml_filename, d_input):
    inputs = d_input.copy()
    yml = {}
    for category in ["Input_parameters"]:
        for item, value in inputs[category].iteritems():
            yml[item] = value
    for category in ["Input_files_data"]:
        for item in inputs[category].keys():
            v = inputs[category][item]
            if v.get('mount', False):
                input_dir = INPUT_MOUNT_DIR_PREFIX + v['dir']
            else:
                input_dir = INPUT_DIR
            if 'mount' in v:
                del v['mount']
            del v['dir']
            if 'profile' in v:
                del v['profile']
            if 'rename' in v and v['rename']:
                if isinstance(v['rename'], list):
                    v['path'] = v['rename'][:]
                else:
                    v['path'] = v['rename']
                del v['rename']
            if 'unzip' in v:
                unzip = v['unzip']
                del v['unzip']
            else:
                unzip = ''
            if isinstance(v['path'], list):
                v2 = []
                for pi in v['path']:
                    if isinstance(pi, list):
                        nested = []
                        for ppi in pi:
                            if isinstance(ppi, list):
                                nested.append([file2cwlfile(pppi, input_dir, unzip) for pppi in ppi])
                            else:
                                nested.append(file2cwlfile(ppi, input_dir, unzip))
                        v2.append(nested)
                    else:
                        v2.append(file2cwlfile(pi, input_dir, unzip))
                v = v2
                yml[item] = v
            else:
                if unzip:
                    v['path'] = re.match('(.+)\.{0}$'.format(unzip), v['path']).group(1)
                v['path'] = input_dir + '/' + v['path']
                yml[item] = v.copy()
    with open(input_yml_filename, 'w') as f_yml:
        json.dump(yml, f_yml, indent=4, sort_keys=True)


def create_input_for_wdl(input_yml_filename, d_input):
    inputs = d_input.copy()
    yml = {}
    for category in ["Input_parameters"]:
        for item, value in inputs[category].iteritems():
            yml[item] = value
    for category in ["Input_files_data"]:
        for item in inputs[category].keys():
            v = inputs[category][item]
            if v.get('mount', False):
                input_dir = INPUT_MOUNT_DIR_PREFIX + v['dir']
            else:
                input_dir = INPUT_DIR
            if 'mount' in v:
                del v['mount']
            if 'rename' in v and v['rename']:
                if isinstance(v['rename'], list):
                    v['path'] = list(v['rename'])
                else:
                    v['path'] = v['rename']
                del v['rename']
            if 'unzip' in v:
                unzip = v['unzip']
                del v['unzip']
            else:
                unzip = ''
            if isinstance(v['path'], list):
                yml[item] = []
                for pi in v['path']:
                    if isinstance(pi, list):
                        nested = []
                        for ppi in pi:
                            if isinstance(ppi, list):
                                nested.append([file2wdlfile(pppi, input_dir, unzip) for pppi in ppi])
                            else:
                                nested.append(file2wdlfile(ppi, input_dir, unzip))
                        yml[item].append(nested)
                    else:
                        yml[item].append(file2wdlfile(pi, input_dir, unzip))
            else:
                if unzip:
                    v['path'] = re.match('(.+)\.{0}$'.format(unzip), v['path']).group(1)
                yml[item] = input_dir + '/' + v['path']
    with open(input_yml_filename, 'w') as f_yml:
        json.dump(yml, f_yml, indent=4, sort_keys=True)


def create_input_for_snakemake(input_yml_filename, d_input):
    pass  # for now assume no input yml


# create a file that defines environmental variables
def create_env_def_file(env_filename, d, language):
    # I have to use these variables after this script finishes running.
    # I didn't use os.environ + os.system('bash') because that would remove the other
    # env variables set before this script started running.
    with open(env_filename, 'w') as f_env:
        if language == 'wdl':
            f_env.write("export WDL_URL={}\n".format(d["Job"]["App"]["wdl_url"]))
            f_env.write("export MAIN_WDL={}\n".format(d["Job"]["App"]["main_wdl"]))
            f_env.write("export WDL_FILES=\"{}\"\n".format(' '.join(d["Job"]["App"]["other_wdl_files"].split(','))))
        elif language == 'snakemake':
            f_env.write("export SNAKEMAKE_URL={}\n".format(d["Job"]["App"]["snakemake_url"]))
            f_env.write("export MAIN_SNAKEMAKE={}\n".format(d["Job"]["App"]["main_snakemake"]))
            f_env.write("export SNAKEMAKE_FILES=\"{}\"\n".format(' '.join(d["Job"]["App"]["other_snakemake_files"].split(','))))
            f_env.write("export COMMAND=\"{}\"\n".format(d["Job"]["App"]["command"].replace("\"", "\\\"")))
            f_env.write("export CONTAINER_IMAGE={}\n".format(d["Job"]["App"]["container_image"]))
        elif language == 'shell':
            f_env.write("export COMMAND=\"{}\"\n".format(d["Job"]["App"]["command"].replace("\"", "\\\"")))
            f_env.write("export CONTAINER_IMAGE={}\n".format(d["Job"]["App"]["container_image"]))
        else:  # cwl
            f_env.write("export CWL_URL={}\n".format(d["Job"]["App"]["cwl_url"]))
            f_env.write("export MAIN_CWL={}\n".format(d["Job"]["App"]["main_cwl"]))
            f_env.write("export CWL_FILES=\"{}\"\n".format(' '.join(d["Job"]["App"]["other_cwl_files"].split(','))))
        # other env variables
        f_env.write("export OUTBUCKET={}\n".format(d["Job"]["Output"]["output_bucket_directory"]))
        f_env.write("export PUBLIC_POSTRUN_JSON={}\n".format('1' if d["config"].get('public_postrun_json', False) else '0'))
        env_preserv_str = ''
        docker_env_str = ''
        if "Env" in d["Job"]["Input"]:
            for ev, val in d["Job"]["Input"]["Env"].iteritems():
                f_env.write("export {}={}\n".format(ev, val))
                env_preserv_str = env_preserv_str + "--preserve-environment " + ev + " "
                docker_env_str = docker_env_str + "-e " + ev + " "
        f_env.write("export PRESERVED_ENV_OPTION=\"{}\"\n".format(env_preserv_str))
        f_env.write("export DOCKER_ENV_OPTION=\"{}\"\n".format(docker_env_str))


if __name__ == '__main__':
    main()
