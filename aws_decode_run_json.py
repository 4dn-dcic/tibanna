#!/usr/bin/python
import json
import sys
import os
import subprocess
 
downloadlist_filename="download_command_list.txt"
input_yml_filename="inputs.yml"
env_filename="env_command_list.txt"
 
## read json file
with open(sys.argv[1],'r') as json_file:
  dict=json.load(json_file)
 
## create a download command list file from the information in json
dict_input = dict["Job"]["Input"]
with open(downloadlist_filename,'w') as f_download:
  for category in ["Input_files_data","Input_files_reference"]:
    keys=dict_input[category].keys()
    for i in range(0,len(dict_input[category])):
      print i
      print keys[i]
      print str(dict_input[category][keys[i]])
      DATA_FILE = dict_input[category][keys[i]]["path"]
      DATA_BUCKET = dict_input[category][keys[i]]["dir"]
      f_download.write("aws s3 cp s3://{0}/{1} {1}\n".format(DATA_BUCKET,DATA_FILE))
 
## create an input yml file for cwl-runner
with open(input_yml_filename,'w') as f_yml:
  inputs = dict_input.copy()
  yml={}
  for category in ["Input_files_data","Input_files_reference"]:
     for item in inputs[category].keys():
       if inputs[category][item].has_key('dir'):
          del inputs[category][item]['dir']
       yml[item]=inputs[category][item].copy()
  json.dump(yml, f_yml, indent=4, sort_keys=True)
 
 
# create a file that defines environmental variables
# I have to use these variables after this script finishes running. I didn't use os.environ + os.system('bash') because that would remove the other env variables set before this script started running.
with open(env_filename,'w') as f_env:
  f_env.write("CWLBUCKET={}\n".format(dict["Job"]["App"]["cwl_directory"]))
  f_env.write("CWL_FILE={}\n".format(dict["Job"]["App"]["main_cwl"]))
  f_env.write("OUTBUCKET={}\n".format(dict["Job"]["Output"]["output_directory"]))
 
