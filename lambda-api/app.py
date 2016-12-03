from __future__ import print_function
from chalice import Chalice

import json
import boto3 ## 1.4.1 (not the default boto3 on lambda)
import requests 
import time
import sys
import random

app = Chalice(app_name="tibanna_lambda_dev")


sbg_project_id = "4dn-dcic/dev"
bucket_for_token = "4dn-dcic-sbg" # an object containing a sbg token is in this bucket 
object_for_token = "token-4dn-labor" # an object containing a sbg token
object_for_access_key = 's3-access-key-4dn-labor'  # an object containing security credentials for a user 'sbg_s3', who has access to 4dn s3 buckets. It's in the same bucket_for_token. Public_key\nsecret_key. We need this not for the purpose of lambda connecting to our s3, but SBG requires it for mounting our s3 bucket to the sbg s3.


class SBGVolume:
  prefix = '4dn_s3'
  account = '4dn-labor'

  def __init__(self, volume_suffix=None):

    if volume_suffix is None:
      volume_suffix=''
      for i in xrange(8):
        r=random.choice('abcdefghijklmnopqrstuvwxyz1234567890')
        volume_suffix += r
  
    self.name = self.prefix + volume_suffix # name of the volume to be mounted on sbg.
    self.id = self.account + '/' + self.name  # ID of the volume to be mounted on sbg.



class SBGTaskInput(object):
  def __init__(self, sbg_project_id, app_name, inputs={}): 
    self.app = sbg_project_id + "/" + app_name
    self.project = sbg_project_id
    self.inputs = inputs

  def toJSON(self):
    return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

  def add_input(self, new_input):
    self.inputs.update(new_input)

  def add_inputfile(self, filename, file_id, argument_name):
    new_input = { argument_name: { "class": "File", "name": filename, "path": file_id } }
    if self.check_validity_inputfile(new_input):
      self.add_input(new_input)
    else:
      print("Error: input format for SBGTaskInput not valid")
      sys.exit()

  def add_inputparam(self, param_name, argument_name):
    new_input = { argument_name: param_name }
    self.add_input(new_input)

  def check_validity_inputfile(self, ip):
    if isinstance(ip, dict) and len(ip)==1 and isinstance(ip.values()[0],dict) and ip.values()[0].has_key('class') and ip.values()[0].has_key('name') and ip.values()[0].has_key('path'):
      return(True)
    else:
      return(False)



class SBGWorkflowRun(object): ## one object per workflow run

  base_url = "https://api.sbgenomics.com/v2"

  def __init__(self, token, project_id):
    self.token=token
    self.header={ "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
    self.project_id=project_id
    self.volume_list=[]  ## list of volumes mounted for the current run. We keep the information here so that they can be deleted later
    self.import_id_list=[]  ## list of import ids for the files imported for the current run.
    self.task_id=None  ## task_id for the current workflow run. It will be assigned after draft task is successfully created. We keep the information here, so we can re-run the task if it fails and also for the sanity check - so that we only run tasks that we created.
    self.task_input=None  ## SBGTaskInput object


  ## function that creates volume
  ## sbg_volume: SBGVolume object
  ## bucket_name: name of bucket to mount
  ## public_key, secret_key: keys for S3 bucket
  ## bucket_object_prefix : for subdirectory inside the bucket, use subdirectory_name+'/'
  ## access_mode : 'ro' for readonly 'rw' for read and write
  def create_volumes (self, sbg_volume, bucket_name, public_key, secret_key, bucket_object_prefix='', access_mode='rw'):
    volume_url = self.base_url + "/storage/volumes/"
    data = {
      "name" : sbg_volume.name,
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

    try:
      response = requests.post(volume_url, headers=self.header, data=json.dumps(data))
      ## update volume_list 
      if sbg_volume not in self.volume_list:
        self.volume_list.append(sbg_volume)
      return(response.json())
    except Exception as e:
      print(e)
      print("volume creation error")
      raise e


  ## function that initiations importing (mounting) an object on 4dn s3 to SBG s3
  ## source_filename : object key on 4dn s3
  ## dest_filename : filename-to-be on SBG s3 (default, it is set to be the same as source_filename) 
  ## return value : the newly imported (mounted) file's ID on SBG S3
  def import_volume_content (self, sbg_volume, object_key, dest_filename=None):
 
    if sbg_volume not in self.volume_list:
      print("Error: the specified volume doesn't exist in the current workflow run.")  
      sys.exit()

    source_filename = object_key
    if dest_filename is None:
       dest_filename = object_key
    import_url = self.base_url + "/storage/imports"
    data = {
      "source":{
        "volume": sbg_volume.id,
        "location": source_filename
      },
      "destination": {
        "project": self.project_id,
        "name": dest_filename
      },
      "overwrite": False
    }
    response = requests.post(import_url, headers=self.header, data=json.dumps(data))

    if response.json().has_key('id'):
      import_id = response.json().get('id')
      if import_id not in self.import_id_list:
        self.import_id_list.append(import_id)
      return(import_id)
    else:
      print("Error: import not successful.")
      sys.exit()  


  ## check the status and other details of import
  def get_details_of_import (self, import_id):

    if import_id not in self.import_id_list:
      print("Error: the import id is not in the SBG workflow run.")
      sys.exit()

    import_url = self.base_url + "/storage/imports/" + import_id
    data = { "import_id" : import_id }
  
    ## wait while import is pending
    while True:
      response = requests.get(import_url, headers=self.header, data=json.dumps(data))
      if response.json().get('state') != 'PENDING':
        break;
      time.sleep(2)
  
    ## if import failed 
    if response.json().get('state') != 'COMPLETED':
      print(response.json())
      sys.exit() 
  
    return(response.json())


  ## create a draft task on SBG, given a SBGTaskInput object  
  def create_task(self, sbg_task_input):
      url = self.base_url + "/tasks"
      data = sbg_task_input.__dict__
      resp = requests.post(url, headers=self.header, data=json.dumps(data))

      if resp.json().has_key('id'):
        self.task_id = resp.json().get('id')
        self.task_input = sbg_task_input
        return(resp.json()) 
      else:
        print(resp.json())
        sys.exit()
  

  ## run task on SBG
  ## A draft task must be created before running it
  def run_task (self):

      if self.task_id is None:
        print("Error: no task_id available. Create a draft task first.")
        sys.exit()

      url = self.base_url + "/tasks/" + self.task_id + "/actions/run"
      data = self.task_input.__dict__
      resp = requests.post(url, headers=self.header, data=json.dumps(data))
      return(resp.json()) ## return the run_task response
  
  
  ## check status of task
  def check_task (self):
      if self.task_id is None:
        print("Error: no task_id available. Create a draft task first.")
        sys.exit()

      url = self.base_url + "/tasks/" + self.task_id
      data = {}
      response = requests.get(url, headers=self.header, data=json.dumps(data))
      return ( response.json() )


  ## example method for creating sbgtaskinput for validate app given the response body of import request in json format
  def create_data_payload_validatefiles ( import_response ):
  
    try:
  
       file_id = import_response.get('result').get('id') # imported Id on SBG
       file_name = import_response.get('result').get('name') # imported file name on SBG
  
       app_name = "validate"  
  
       sbgtaskinput = SBGTaskInput(self.project_id, app_name)
       sbgtaskinput.add_inputfile(file_name, file_id, "input_file")
       sbgtaskinput.add_inputparam("fastq","type")
  
       return(sbgtaskinput)
  
    except Exception as e:
       print(e)
       print('Error creating a task payload')
       raise e 



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



@app.route("/run",methods=['POST'])
def RUN():

    event = app.current_request.json_body

    input_file_list = event.get('input_files')
    app_name = event.get('app_name').encode('utf8')
    parameter_dict = event.get('parameters')


    ## get s3 resource 
    ## check the bucket and key
    try:
        s3 = boto3.resource('s3')

    except Exception as e:
        print(e)
        print('Error getting S3 resource')
        raise e
 

    ## get token and access key
    try:
        token = get_sbg_token(s3)
        access_key = get_access_key(s3)

    except Exception as e:
        print(e)
        print('Error getting token and access key from bucket {}.'.format(bucket))
        raise e

    ## create a sbg workflow run object to use
    sbg = SBGWorkflowRun(token,sbg_project_id)

    ## mount multiple input files to SBG S3 and
    ## create a SBGTaskInput object that contains multiple files and given parameters
    task_input = SBGTaskInput(sbg_project_id, app_name, parameter_dict)
    for e in input_file_list:

        bucket = e.get('bucket_name').encode('utf8')
        key = e.get('object_key').encode('utf8')
        workflow_argument = e.get('workflow_argument_name').encode('utf8')
    
        ## check the bucket and key
        try:
            response = s3.Object(bucket, key)
        except Exception as e:
            print(e)
            print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
            raise e
    
        ## mount the bucket and import the file
        try: 
            sbg_volume = SBGVolume()
            sbg_create_volume_response = sbg.create_volumes (sbg_volume, bucket, public_key=access_key[0], secret_key=access_key[1])
            print(sbg_create_volume_response)  ## DEBUGGING
            sbg_import_id = sbg.import_volume_content (sbg_volume, key)
            print(sbg_import_id)
            sbg_check_import_response = sbg.get_details_of_import(sbg_import_id)
            print(sbg_check_import_response)
            
        except Exception as e:
            print(e)
            print('Error mounting/importing the file to SBG') 
            raise e

        ## add to task input
        try:
            sbg_file_name = sbg_check_import_response.get('result').get('name')
            sbg_file_id = sbg_check_import_response.get('result').get('id')
            task_input.add_inputfile( sbg_file_name, sbg_file_id, workflow_argument )
        
        except Exception as e:
            print(e)
            print('Error mounting/importing the file to SBG') 
            raise e 


    # run a validatefiles task 
    try:
        #task_data = sbg.create_data_payload_validatefiles( sbg_check_import_response)
        create_task_response = sbg.create_task( task_input )
        run_response = sbg.run_task()

    except Exception as e:
        print(e)
        print('Error running a task')
        raise e
    

    # check task
    try:
        check_task_response = sbg.check_task()
        return( check_task_response )

    except Exception as e:
        print(e)
        print('Error running a task')
        raise e
    
    # for debugging
    try:
        print(json.dumps(sbg.__dict__))
    except Exception as e:
        print(e)
        print("Error printing the SBGWorkflowRun object.")
        raise e



if __name__ == "__main__":
   print ("haha")

