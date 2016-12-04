from __future__ import print_function

import json
import urllib
import boto3 ## 1.4.1 (not the default boto3 on lambda)
import requests 
import time
import sys
import random

sbg_base_url = "https://api.sbgenomics.com/v2"
sbg_project_id = "4dn-dcic/dev"
bucket_for_token = "4dn-dcic-sbg" # an object containing a sbg token is in this bucket 
object_for_token = "token-4dn-labor" # an object containing a sbg token
volume_name = '4dn_s3' # name of the volume to be mounted on sbg.
volume_id = '4dn-labor/' + volume_name # ID of the volume to be mounted on sbg.
object_for_access_key = 's3-access-key-4dn-labor'  # an object containing security credentials for a user 'sbg_s3', who has access to 4dn s3 buckets. It's in the same bucket_for_token. Public_key\nsecret_key. We need this not for the purpose of lambda connecting to our s3, but SBG requires it for mounting our s3 bucket to the sbg s3.


## function that grabs SBG token from a designated S3 bucket
def get_sbg_token (s3):
  try:
    s3.Bucket(bucket_for_token).download_file(object_for_token,'/tmp/'+ object_for_token)  ## lambda doesn't have write access to every place, so use /tmp/.
    with open('/tmp/' + object_for_token,'r') as f:  
      token = f.readline().rstrip()
    return token
  except Exception as e:
    print(e)
    print('Error getting token from S3.')
    raise e


def get_access_key (s3):
  try:
    s3.Bucket(bucket_for_token).download_file(object_for_access_key,'/tmp/'+ object_for_access_key)
    with open('/tmp/' + object_for_access_key,'r') as f:
      access_key = f.read().splitlines()
    return access_key

  except Exception as e:
    print(e)
    print('Error getting access key from S3.')
    raise e


## function that returns a requests response in a nicely indented json format.
def format_response (response):
  return json.dumps(json.loads(response.text), indent=4)


## function that creates volume
def create_volumes (token, volume_name, bucket_name, public_key, secret_key, bucket_object_prefix='', access_mode='rw'):
  volume_url = sbg_base_url + "/storage/volumes/"
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = {
    "name" : volume_name,
    "description" : "some volume" ,
    "service" : {
       "type": "s3",
       "bucket": bucket_name,
       "prefix": bucket_object_prefix, ## prefix of objects, this causs some confusion later when referring to the mounted file, because you have to exclude the prefix part, so just keep it as ''. 
       "credentials": {
         "access_key_id": public_key, ## public access key for our s3 bucket
         "secret_access_key": secret_key  ## secret access key for our s3 bucket
       },
       "properties": {
         "sse_algorithm": "AES256"
       }
    },
    "access_mode" : access_mode  ## either 'rw' or 'ro'.
  }
  response = requests.post(volume_url, headers=header, data=json.dumps(data))
  return(format_response(response))




## function that initiations importing (mounting) an object on 4dn s3 to SBG s3
## token : SBG authentication token
## volume_id : the volume-to-be on SBG s3, e.g. duplexa/myvolume3 (it looks like the first part (duplexa) should match the ownder of the token.)
## source_filename : object key on 4dn s3
## dest_filename : filename-to-be on SBG s3 (default, it is set to be the same as source_filename) 
## return value : the newly imported (mounted) file's ID on SBG S3
def import_volume_content (token, volume_id, object_key, dest_filename=None):

  source_filename = object_key
  if dest_filename is None:
     dest_filename = object_key
  import_url = sbg_base_url + "/storage/imports"
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = {
    "source":{
      "volume": volume_id,
      "location": source_filename
    },
    "destination": {
      "project": sbg_project_id,
      "name": dest_filename
    },
    "overwrite": False
  }
  response = requests.post(import_url, headers=header, data=json.dumps(data))
  return(response.json()['id'])



def get_details_of_import (token, import_id):
  import_url = sbg_base_url + "/storage/imports/" + import_id
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = { "import_id" : import_id }

  ## wait while import is pending
  while True:
    response = requests.get(import_url, headers=header, data=json.dumps(data))
    if response.json()['state'] != 'PENDING':
      break;
    time.sleep(2)

  ## if import failed 
  if response.json()['state'] != 'COMPLETED':
    print(response.json())
    sys.exit() 

  return(response.json())


def create_data_payload_validatefiles ( import_response ):

  try:

     file_id = import_response['result']['id'] # imported Id on SBG
     file_name = import_response['result']['name'] # imported file name on SBG

     app_name = "validate"  

     data = { "app": sbg_project_id + "/" + app_name,
              "project": sbg_project_id,
              "inputs": {
                 "input_file": {
                   "class": "File",
                   "path": file_id,
                   "name": file_name
                 },
                 "type": "fastq"
              } 
            }
     return(data)

  except Exception as e:
     print(e)
     print('Error creating a task payload')
     raise e 


def create_task(token, data):
    url = sbg_base_url + "/tasks"

    headers = {'X-SBG-Auth-Token': token,
               'Content-Type': 'application/json'}

    resp = requests.post(url, headers=headers, data=json.dumps(data))
    print(resp.json())

    if resp.json().has_key('id'):
      return(resp.json()) 
    else:
      print(resp.json())
      sys.exit()


def run_task (token, create_task_response):
    task_id = create_task_response['id']
    url = sbg_base_url + "/tasks/" + task_id + "/actions/run"
    headers = {'X-SBG-Auth-Token': token,
               'Content-Type': 'application/json'}

    data = create_task_response['inputs']
    resp = requests.post(url, headers=headers, data=json.dumps(data))
    return(resp.json()) ## return the run_task response


## This function is TEMPORARY - most of the jobs will run for more than the lifespan of this lambda function.
## Use it for test purpose for a tiny input file.
def check_task (token, task_id):
    url = sbg_base_url + "/tasks/" + task_id
    headers = {'X-SBG-Auth-Token': token,
               'Content-Type': 'application/json'}

    data = {}
    resp = requests.get(url, headers=headers, data=json.dumps(data))

    ## wait while task is pending
    response = requests.get(url, headers=headers, data=json.dumps(data))
    return ( response.json() )



def export_to_volume (token, source_file_id, volume_id, dest_filename):
  export_url = sbg_base_url + "/storage/exports/"
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = {
    "source": {
      "file": source_file_id
    },
    "destination": {
      "volume": volume_id,
      "location": dest_filename
    }
  }
  response = requests.post(export_url, headers=header, data=json.dumps(data))
  
  if response.json().has_key('id'):
    return(response.json()['id'])
  else:
    print("Export error")
    print(response)
    sys.exit()

def check_export (token, export_id):
  export_url = sbg_base_url + "/storage/exports/" + export_id
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = { "export_id" : export_id }

  response = requests.get(export_url, headers=header, data=json.dumps(data))
  return(response.json())


def get_export_status (token, export_id):
  result = check_export(token, export_id)
  if result.has_key('state'):
    return check_export(token, export_id)['state']
  else:
    return None


def generate_uuid ():
  rand_uuid_start=''
  for i in xrange(8):
    r=random.choice('abcdef1234567890')
    rand_uuid_start += r
    uuid=rand_uuid_start + "-49e5-4c33-afab-9ec90d65faf3"
  return uuid

def generate_rand_accession ():
  rand_accession=''
  for i in xrange(8):
    r=random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890')
    rand_accession += r
    accession = "4DNF"+rand_accession
  return accession


# This function returns a new workflow_run dictionary; it should be updated so that existing workflow_run objects are modified.
# Input files are omitted here. They should already be in the workflow_run.
def fill_workflow_run(sbg_run_detail_resp, processed_files_report, bucket_name, output_only=True):

  workflow_run={ 'uuid':generate_uuid(), 'input_files':[], 'output_files':[], 'parameters':[] }
  processed_files = []  

  report_dict = sbg_run_detail_resp

  if output_only:
     file_type_list = ['outputs']  ## transfer only output files
  else:
     file_type_list = ['inputs','outputs']  ## transfer both input and output files

  # input/output files
  # export files to s3, add to file metadata json, add to workflow_run dictionary
  for file_type in file_type_list:
    if file_type=='inputs':
       workflow_run_file_type='input_files'
    else:
       workflow_run_file_type='output_files'
       
    for k,v in report_dict.get(file_type).iteritems():
      if isinstance(v,dict) and v.get('class')=='File':   ## This is a file
         sbg_filename = v['name']
         uuid = processed_files_report[sbg_filename]['uuid']
         workflow_run[workflow_run_file_type].append({'workflow_argument_name':k, 'value':uuid})

      elif isinstance(v,list):
         for v_el in v:
            if isinstance(v_el,dict) and v_el.get('class')=='File':  ## This is a file (v is an array of files)
               sbg_filename = v['name']
               uuid = processed_files_report[sbg_filename]['uuid']
               workflow_run[workflow_run_file_type].append({'workflow_argument_name':k, 'value':uuid})

  # parameters
  # add to workflow_run dictionary
  # assuming that parameters in the sbg report are either a single value or an array of single values.
  for k,v in report_dict.get('inputs').iteritems():
     if not isinstance(v,dict) and not isinstance(v,list):
        workflow_run['parameters'].append({'workflow_argument_name':k, 'value':v})
     if isinstance(v,list):
        for v_el in v:
           if not isinstance(v_el,dict):
              workflow_run['parameters'].append({'workflow_argument_name':k, 'value':v_el})

  return (workflow_run)  ## later change to actually 'updating metadata'



# Initiate exporting all output files to S3 and returns an array of {filename, export_id} dictionary
# export_id should be used to track export status.
def export_all_output_files(token, sbg_run_detail_resp):

  export_report = []

  workflow_run_file_type='output_files'
  file_type = 'outputs'

  # export all output files to s3
  for k,v in sbg_run_detail_resp.get(file_type).iteritems():
    if isinstance(v,dict) and v.get('class')=='File':   ## This is a file
       sbg_file_id = v['path'].encode('utf8')
       sbg_filename = v['name'].encode('utf8')
       export_id = export_to_volume (token, sbg_file_id, volume_id, sbg_filename)
       export_report.append( {"filename":sbg_filename, "export_id":export_id } )


    elif isinstance(v,list):
       for v_el in v:
          if isinstance(v_el,dict) and v_el.get('class')=='File':  ## This is a file (v is an array of files)
             sbg_file_id = v['path'].encode('utf8')
             sbg_filename = v['name'].encode('utf8')
             export_id = export_to_volume (token, sbg_file_id, volume_id, sbg_filename)
             export_report.append( {"filename":sbg_filename, "export_id":export_id } )

  return ( export_report) ## array of dictionaries



def fill_processed_files(token, export_report, bucket_name):

  processed_files=[]
  fill_report={}

  for file in export_report:
    filename = file['filename']
    export_id = file['export_id']
    status = get_export_status(token, export_id)

    accession=generate_rand_accession()
    uuid=generate_uuid()

    fill_report[filename]={"export_id":export_id,"status":status,"accession":accession,"uuid":uuid}

    # create a meta data file object
    metadata= {
      "accession": accession,
      "filename": 's3://' + bucket_name + '/' + filename,
      "notes": "sample dcic notes",
      "lab": "4dn-dcic-lab",
      "submitted_by": "admin@admin.com",
      "lab": "4dn-dcic-lab",
      "award": "1U01CA200059-01",
      "file_format": "other",
      #"experiments":["4DNEX067APT1"],
      "uuid": uuid,
      "status": "export " + status
    }

    processed_files.append(metadata)

  return ({"metadata":processed_files,"report": fill_report })



def lambda_handler(event, context):
    #print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event and show its content type
    task_id = event['task_id'].encode('utf8')   
    bucket = event['bucket_name'].encode('utf8')

    try:
        s3 = boto3.resource('s3')
    except Exception as e:
        print(e)
        print("Error creating an S3 resource")
        raise e 

    ## get token and access key
    try:
        token = get_sbg_token(s3)
        access_key = get_access_key(s3)

    except Exception as e:
        print(e)
        print('Error getting token and access key from bucket {}.'.format(bucket))
        raise e
    

    # check task 
    try:
        check_task_response = check_task (token, task_id)

    except Exception as e:
        print(e)
        print('Error running a task')
        raise e
    

    run_status = check_task_response['status'] 
    if run_status == 'COMPLETED' or run_status == 'FAILED':

      ## mount the output bucket (silent if already mounted)
      try: 
         sbg_create_volume_response = create_volumes (token, volume_name, bucket, public_key=access_key[0], secret_key=access_key[1])
        
      except Exception as e:
         print(e)
         print('Error mounting output bucket to SBG') 
         raise e


      ## initiate output file export and fill in metadata
      try:
         export_report = export_all_output_files(token, check_task_response)  #array of {filename, export_id}
         time.sleep(10)  # give some time so that small files can be finished exporting before checking export status.
         processed_files_result = fill_processed_files(token, export_report, bucket)
         print(str(processed_files_result))  ## DEBUGGING
         metadata_processed_files = processed_files_result['metadata']
         print(str(metadata_processed_files))  ## DEBUGGING
         metadata_workflow_run = fill_workflow_run(check_task_response, processed_files_result['report'], bucket)
         return ( { "workflow_run": metadata_workflow_run, "processed_files": metadata_processed_files } )
  
      except Exception as e:
          print(e)
          print('Error exporting output files')
          raise e

    else:
      metadata_workflow_run = fill_workflow_run(check_task_response, [], bucket)
      metadata_workflow_run['status'] = run_status
      return ( { "workflow_run": metadata_workflow_run, "processed_files": []} )


if __name__ == "__main__":
   print ("haha")

