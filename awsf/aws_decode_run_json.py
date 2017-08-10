#!/usr/bin/python
import json
import sys
import os
import subprocess
 
downloadlist_filename="download_command_list.txt"
input_yml_filename="inputs.yml"
env_filename="env_command_list.txt"
input_dir="/data1/input"
reference_dir="/data1/reference" 

## read json file
with open(sys.argv[1], 'r') as json_file:
    dict=json.load(json_file)
 
## create a download command list file from the information in json
dict_input = dict["Job"]["Input"]
with open(downloadlist_filename, 'w') as f_download:
    for category in ["Input_files_data", "Input_files_reference"]:
        keys=dict_input[category].keys()
        if category=="Input_files_data":
            LOCAL_DIR=input_dir
        else:
            LOCAL_DIR=reference_dir
        for i in range(0, len(dict_input[category])):
            DATA_BUCKET = dict_input[category][keys[i]]["dir"]
            if isinstance(dict_input[category][keys[i]]["path"], list):
                for file in dict_input[category][keys[i]]["path"]:
                    DATA_FILE = file
                    f_download.write("aws s3 cp s3://{0}/{1} {2}/{1}\n".format(DATA_BUCKET, DATA_FILE, LOCAL_DIR))
            else:    
                DATA_FILE = dict_input[category][keys[i]]["path"]
                f_download.write("aws s3 cp s3://{0}/{1} {2}/{1}\n".format(DATA_BUCKET, DATA_FILE, LOCAL_DIR))
 
## create an input yml file for cwl-runner
with open(input_yml_filename, 'w') as f_yml:
    inputs = dict_input.copy()
    yml={}
    for category in ["Input_parameters"]:
         for item, value in inputs[category].iteritems():
             yml[item]=value
    for category in ["Input_files_data", "Input_files_reference"]:
         if category=="Input_files_data":
                LOCAL_DIR=input_dir
         else:
                LOCAL_DIR=reference_dir
         for item in inputs[category].keys():
             v=inputs[category][item]
             if v.has_key('dir'):
                    del v['dir']
             if isinstance(v['path'], list):
                    v2=[]
                    for i in range(0, len(v['path'])):
                        v2.append ( { "class": v['class'], "path": LOCAL_DIR + '/' + v['path'][i] } )
                    v=v2
                    yml[item]=v
             else:
                    v['path']=LOCAL_DIR + '/' + v['path']
                    yml[item]=v.copy()
    json.dump(yml, f_yml, indent=4, sort_keys=True)
 
 
# create a file that defines environmental variables
# I have to use these variables after this script finishes running. I didn't use os.environ + os.system('bash') because that would remove the other env variables set before this script started running.
with open(env_filename, 'w') as f_env:
    f_env.write("CWL_URL={}\n".format(dict["Job"]["App"]["cwl_url"]))
    f_env.write("MAIN_CWL={}\n".format(dict["Job"]["App"]["main_cwl"])) ## main cwl to be run (the other cwl files will be called by this one)
    f_env.write("CWL_FILES=\"{}\"\n".format(' '.join(dict["Job"]["App"]["other_cwl_files"].split(',')))) ## list of cwl files in an array delimited by a space
    f_env.write("OUTBUCKET={}\n".format(dict["Job"]["Output"]["output_bucket_directory"]))
 

