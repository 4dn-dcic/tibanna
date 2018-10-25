#!/usr/bin/python
import json
import sys

downloadlist_filename = "download_command_list.txt"
input_yml_filename = "inputs.yml"
env_filename = "env_command_list.txt"
INPUT_DIR = "/data1/input"


def main():
    # read json file
    with open(sys.argv[1], 'r') as json_file:
        Dict = json.load(json_file)
        Dict_input = Dict["Job"]["Input"]
        language = Dict["Job"]["App"]["language"]
    # create a download command list file from the information in json
    create_download_command_list(downloadlist_filename, Dict_input)
    # create an input yml file to be used on awsem
    if language == 'wdl':  # wdl
        create_input_for_wdl(input_yml_filename, Dict_input)
    else:  # cwl
        create_input_for_cwl(input_yml_filename, Dict_input)
    # create a file that defines environmental variables
    create_env_def_file(env_filename, Dict, language)


def add_download_cmd(data_bucket, data_file, input_dir, profile_flag, f):
    cmd = "aws s3 cp s3://{0}/{1} {2}/{1} {3}\n"
    f.write(cmd.format(data_bucket, data_file, input_dir, profile_flag))


# create a download command list file from the information in json
def create_download_command_list(downloadlist_filename, Dict_input):
    with open(downloadlist_filename, 'w') as f_download:
        for category in ["Input_files_data", "Secondary_files_data"]:
            keys = Dict_input[category].keys()
            for i in range(0, len(Dict_input[category])):
                DATA_BUCKET = Dict_input[category][keys[i]]["dir"]
                PROFILE = Dict_input[category][keys[i]].get("profile", '')
                PROFILE_FLAG = "--profile " + PROFILE if PROFILE else ''
                path1 = Dict_input[category][keys[i]]["path"]
                if isinstance(path1, list):
                    for path2 in path1:
                        if isinstance(path2, list):
                            for path3 in path2:
                                if isinstance(path3, list):
                                    for data_file in path3:
                                        add_download_cmd(DATA_BUCKET, data_file, INPUT_DIR, PROFILE_FLAG, f_download)
                                else:
                                    data_file = path3
                                    add_download_cmd(DATA_BUCKET, data_file, INPUT_DIR, PROFILE_FLAG, f_download)
                        else:
                            data_file = path2
                            add_download_cmd(DATA_BUCKET, data_file, INPUT_DIR, PROFILE_FLAG, f_download)
                else:
                    data_file = path1
                    add_download_cmd(DATA_BUCKET, data_file, INPUT_DIR, PROFILE_FLAG, f_download)


def file2cwlfile(filename, dir):
    return {"class": 'File', "path": dir + '/' + filename}


# create an input yml file for cwl-runner
def create_input_for_cwl(input_yml_filename, Dict_input):
    with open(input_yml_filename, 'w') as f_yml:
        inputs = Dict_input.copy()
        yml = {}
        for category in ["Input_parameters"]:
            for item, value in inputs[category].iteritems():
                yml[item] = value
        for category in ["Input_files_data"]:
            for item in inputs[category].keys():
                v = inputs[category][item]
                if 'dir' in v:
                    del v['dir']
                if 'profile' in v:
                    del v['profile']
                if isinstance(v['path'], list):
                    v2 = []
                    for pi in v['path']:
                        if isinstance(pi, list):
                            v2.append([file2cwlfile(ppi, INPUT_DIR) for ppi in pi])
                        else:
                            v2.append(file2cwlfile(pi, INPUT_DIR))
                    v = v2
                    yml[item] = v
                else:
                    v['path'] = INPUT_DIR + '/' + v['path']
                    yml[item] = v.copy()
        json.dump(yml, f_yml, indent=4, sort_keys=True)


def create_input_for_wdl(input_yml_filename, Dict_input):
    with open(input_yml_filename, 'w') as f_yml:
        inputs = Dict_input.copy()
        yml = {}
        for category in ["Input_parameters"]:
            for item, value in inputs[category].iteritems():
                yml[item] = value
        for category in ["Input_files_data"]:
            for item in inputs[category].keys():
                v = inputs[category][item]
                if isinstance(v['path'], list):
                    yml[item] = []
                    for pi in v['path']:
                      if isinstance(pi, list):
                          nested = []
                          for ppi in pi:
                              if isinstance(ppi, list):
                                  nested.append([INPUT_DIR + '/' + pppi for pppi in ppi])
                              else:
                                  nested.append(INPUT_DIR + '/' + ppi)
                          yml[item].append(nested)
                      else:
                          yml[item].append(INPUT_DIR + '/' + pi)
                else:
                    yml[item] = INPUT_DIR + '/' + v['path']
        json.dump(yml, f_yml, indent=4, sort_keys=True)


# create a file that defines environmental variables
def create_env_def_file(env_filename, Dict, language):
    # I have to use these variables after this script finishes running.
    # I didn't use os.environ + os.system('bash') because that would remove the other
    # env variables set before this script started running.
    with open(env_filename, 'w') as f_env:
        if language == 'wdl':
            f_env.write("WDL_URL={}\n".format(Dict["Job"]["App"]["wdl_url"]))
            # main cwl to be run (the other cwl files will be called by this one)
            f_env.write("MAIN_WDL={}\n".format(Dict["Job"]["App"]["main_wdl"]))
            # list of cwl files in an array delimited by a space
            f_env.write("WDL_FILES=\"{}\"\n".format(' '.join(Dict["Job"]["App"]["other_wdl_files"].split(','))))
        else:  # cwl
            f_env.write("CWL_URL={}\n".format(Dict["Job"]["App"]["cwl_url"]))
            # main cwl to be run (the other cwl files will be called by this one)
            f_env.write("MAIN_CWL={}\n".format(Dict["Job"]["App"]["main_cwl"]))
            # list of cwl files in an array delimited by a space
            f_env.write("CWL_FILES=\"{}\"\n".format(' '.join(Dict["Job"]["App"]["other_cwl_files"].split(','))))
        # other env variables
        f_env.write("OUTBUCKET={}\n".format(Dict["Job"]["Output"]["output_bucket_directory"]))
        f_env.write("PUBLIC_POSTRUN_JSON={}\n".format('1' if Dict["config"].get('public_postrun_json', False) else '0'))
        env_preserv_str = ''
        if "Env" in Dict["Job"]["Input"]:
            for ev, val in Dict["Job"]["Input"]["Env"].iteritems():
                f_env.write("{}={}\n".format(ev, val))
                env_preserv_str = env_preserv_str + "--preserve-environment " + ev + " "
        f_env.write("PRESERVED_ENV_OPTION=\"{}\"\n".format(env_preserv_str))


main()
