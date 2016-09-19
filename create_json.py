#!/usr/bin/python
import json
import sys
import time
import random
import string
import os
import argparse

## random string generator
def randomword(length):
  return ''.join(random.choice(string.lowercase+string.uppercase+string.digits) for i in range(length))

def create_jobid ():
  return randomword(12)  # date+random_string

def get_start_time ():
  return time.strftime("%Y%m%d-%H:%M:%S")

def create_json_filename (jobid,json_dir):
  return json_dir + '/' + jobid + '.run.json'
 


def run( a, json_dir, jobid ):  # a is the final_args dictionary. json_dir is the output directory for the json file

  ## create jobid here
  if not jobid:
    jobid = create_jobid()

  ## start time
  start_time = get_start_time()

  ##  pre is a dictionary to be printed as a pre-run json file.
  pre = {  'JOBID': jobid,
           'App': {
              'App_name': a['app_name'],
              'App_version': a['app_version'],
              'cwl_url': a['cwl_directory'],
              'main_cwl': a['cwl'],
              'other_cwl_files': a['cwl_children']
           },
           'Input': {
              'Input_files_data': {},  ## fill in later (below)
              'Input_files_reference': {},   ## fill in later (below)
              'Input_parameters': a['input_parameters']
           },
           'Output': {
              'output_bucket_directory': a['output_bucket_directory']
           },
           'Instance_type': a['instance_type'],
           'EBS_SIZE': a['storage_size'],
           'EBS_TYPE': 'io1',
           'EBS_IOPS': a['storage_iops'],
           "AMI_ID": "ami-78c13615",
           "start_time" : start_time
        }

  # fill in input_files and input_reference_files (restructured)
  for item,value in a['input_files'].iteritems():
    pre['Input']['Input_files_data'][item]={'class':'File','dir':a['input_files_directory'],'path':value}
  for item,value in a['input_reference_files'].iteritems():
    pre['Input']['Input_files_reference'][item]={'class':'File','dir':a['input_reference_files_directory'],'path':value}

  # wrap
  pre={ 'Job': pre }

  ## writing to a json file
  json_filename = create_json_filename(jobid, json_dir)
  try:
    os.stat(json_dir)
  except:
    os.makedirs(json_dir) 

  ## write to new json file
  with open(json_filename,'w') as json_new_f:
    json.dump(pre,json_new_f,indent=4,sort_keys=True)


  ## print JOBID
  print(jobid)



## main
parser = argparse.ArgumentParser()

parser.add_argument("-c", "--cwl", help="main cwl file name")
parser.add_argument("-cd", "--cwl_directory", help="the url and subdirectories for the main cwl file (default xxx)")
parser.add_argument("-co", "--cwl_children", help="names of the other cwl files used by main cwl file, delimiated by comma")
parser.add_argument("-a", "--app_name", help="name of the app")
parser.add_argument("-av", "--app_version", help="version of the app")
parser.add_argument("-i", "--input_files", help="input files in json format (parametername:filename)")
parser.add_argument("-ir", "--input_reference_files", help="input reference files in json format (parametername:filename)")
parser.add_argument("-ip", "--input_parameters", help="input parameters in json format (parametername:value)")
parser.add_argument("-id", "--input_files_directory", help="bucket name and subdirectory for input files")
parser.add_argument("-ird", "--input_reference_files_directory", help="bucket name and subdirectory for input reference files")
parser.add_argument("-o", "--output_bucket_directory", help="bucket name and subdirectory for output files and logs")
parser.add_argument("-t", "--instance_type", help="EC2 instance type (default i2.xlarge)")
parser.add_argument("-s", "--storage_size", help="EBS storage size in GB (default 100)")
parser.add_argument("-IO", "--storage_iops", help="EBS storage IOPS (default 5000)")
parser.add_argument("-jd", "--json_dir", help="Local directory in which the output json file will be written (default ./json)")
parser.add_argument("-J", "--job_id", help="Manually assign job ID as specififed (default: randomly generated)")


args = parser.parse_args()

## default values
final_args={
 'cwl': '',  ## required
 'cwl_directory': '', ## required, fill in later, after we set up a github account for this
 'cwl_children': [],
 'app_name': '',
 'app_version': '',
 'input_files': {},
 'input_reference_files': {},
 'input_parameters': {},
 'input_files_directory': '', ## required if input_files is not null
 'innput_reference_files_directory': '', ## required if input_reference_files is not null
 'output_bucket_directory': '',  ## required
 'instance_type': 'i2.xlarge',
 'storage_size': 100,
 'storage_iops': 5000
}
json_dir='./json'

if args.cwl:
  final_args['cwl']=args.cwl
else: 
  sys.exit("cwl field is required")

if args.cwl_directory:
  final_args['cwl_directory']=args.cwl_directory

if args.cwl_children:
  final_args['cwl_children']=args.cwl_children.split(',')

if args.app_name:
  final_args['app_name']=args.app_name

if args.app_version:
  final_args['app_version']=args.app_version

if args.input_files:
  final_args['input_files']=json.loads(args.input_files)

if args.input_reference_files:
  final_args['input_reference_files']=json.loads(args.input_reference_files)

if args.input_parameters:
  final_args['input_parameters']=json.loads(args.input_parameters)

if args.input_files_directory:
  final_args['input_files_directory'] = args.input_files_directory
elif bool(final_args['input_files']):
  sys.exit("input_files_directory must be provided if input_files is provided.")

if args.input_reference_files_directory:
  final_args['input_reference_files_directory'] = args.input_reference_files_directory
elif bool(final_args['input_reference_files']):
  sys.exit("input_reference_files_directory must be provided if input_reference_files is provided.")

if args.output_bucket_directory:
  final_args['output_bucket_directory']=args.output_bucket_directory

if args.instance_type:
  final_args['instance_type']=args.instance_type

if args.storage_size:
  final_args['storage_size']=int(args.storage_size)

if args.storage_iops:
  final_args['storage_iops']=int(args.storage_iops)

if args.json_dir:
  json_dir=args.json_dir

run(final_args, json_dir, args.job_id)





