#!/usr/bin/python
import json
import sys

downloadlist_filename = "download_command_list.txt"
input_yml_filename = "inputs.yml"
env_filename = "env_command_list.txt"
INPUT_DIR = "/data1/input"

# read json file
with open(sys.argv[1], 'r') as json_file:
    Dict = json.load(json_file)

# create a download command list file from the information in json
Dict_input = Dict["Job"]["Input"]
with open(downloadlist_filename, 'w') as f_download:
    for category in ["Input_files_data", "Secondary_files_data"]:
        keys = Dict_input[category].keys()
        for i in range(0, len(Dict_input[category])):
            DATA_BUCKET = Dict_input[category][keys[i]]["dir"]
            PROFILE = Dict_input[category][keys[i]].get("profile", '')
            PROFILE_FLAG = "--profile " + PROFILE if PROFILE else ''
            if isinstance(Dict_input[category][keys[i]]["path"], list):
                for file in Dict_input[category][keys[i]]["path"]:
                    DATA_FILE = file
                    download_cmd = "aws s3 cp s3://{0}/{1} {2}/{1} {3}\n".format(DATA_BUCKET,
                                                                                 DATA_FILE,
                                                                                 INPUT_DIR,
                                                                                 PROFILE_FLAG)
                    f_download.write(download_cmd)
            else:
                DATA_FILE = Dict_input[category][keys[i]]["path"]
                download_cmd = "aws s3 cp s3://{0}/{1} {2}/{1} {3}\n".format(DATA_BUCKET,
                                                                             DATA_FILE,
                                                                             INPUT_DIR,
                                                                             PROFILE_FLAG)
                f_download.write(download_cmd)

# create an input yml file for cwl-runner
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
                for i in range(0, len(v['path'])):
                    v2.append({"class": v['class'], "path": INPUT_DIR + '/' + v['path'][i]})
                v = v2
                yml[item] = v
            else:
                v['path'] = INPUT_DIR + '/' + v['path']
                yml[item] = v.copy()
    json.dump(yml, f_yml, indent=4, sort_keys=True)


# create a file that defines environmental variables
# I have to use these variables after this script finishes running.
# I didn't use os.environ + os.system('bash') because that would remove the other
# env variables set before this script started running.
with open(env_filename, 'w') as f_env:
    f_env.write("CWL_URL={}\n".format(Dict["Job"]["App"]["cwl_url"]))
    # main cwl to be run (the other cwl files will be called by this one)
    f_env.write("MAIN_CWL={}\n".format(Dict["Job"]["App"]["main_cwl"]))
    # list of cwl files in an array delimited by a space
    f_env.write("CWL_FILES=\"{}\"\n".format(' '.join(Dict["Job"]["App"]["other_cwl_files"].split(','))))
    f_env.write("OUTBUCKET={}\n".format(Dict["Job"]["Output"]["output_bucket_directory"]))
    f_env.write("PUBLIC_POSTRUN_JSON={}\n".format('1' if Dict["config"].get('public_postrun_json', False) else '0'))
