from __future__ import print_function
from chalice import Chalice

import wranglertools.fdnDCIC as fdnDCIC
import os
import json
import boto3 ## 1.4.1 (not the default boto3 on lambda)
import requests 
import time
import sys
import random
import datetime

app = Chalice(app_name="tibanna_lambda_api")

sbg_base_url = "https://api.sbgenomics.com/v2"
sbg_project_id = "4dn-dcic/dev"
bucket_for_token = "4dn-dcic-sbg" # an object containing a sbg token is in this bucket 
object_for_token = "token-4dn-labor" # an object containing a sbg token
object_for_access_key = 's3-access-key-4dn-labor'    # an object containing security credentials for a user 'sbg_s3', who has access to 4dn s3 buckets. It's in the same bucket_for_token. Public_key\nsecret_key. We need this not for the purpose of lambda connecting to our s3, but SBG requires it for mounting our s3 bucket to the sbg s3.
bucket_for_keypairs = "4dn-dcic-sbg" # an object containing a sbg token is in this bucket 
#object_for_keypairs = "local_keypairs.json" # an object containing a sbg token
object_for_keypairs = "test_keypairs.json" # an object containing a sbg token


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
        self.id = self.account + '/' + self.name    # ID of the volume to be mounted on sbg.



class SBGTaskInput(object):
    def __init__(self, sbg_project_id, app_name, input_param={}): 
        self.app = sbg_project_id + "/" + app_name
        self.project = sbg_project_id
        self.inputs = {}
        for k,v in input_param.iteritems():
            if isinstance(k, (str, unicode)):
                k= k.encode('utf-8')
            if isinstance(v, (str, unicode)):
                v= v.encode('utf-8')
            self.add_inputparam(v, k)

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
        if isinstance(ip, dict) and len(ip)==1 and isinstance(ip.values()[0], dict) and ip.values()[0].has_key('class') and ip.values()[0].has_key('name') and ip.values()[0].has_key('path'):
            return(True)
        else:
            return(False)



class WorkflowRunMetadata(object):
    def __init__(self, workflow_uuid, metadata_input=[], metadata_parameters=[]):
        """Class for WorkflowRun that matches the 4DN Metadata schema
        Workflow_uuid (uuid of the workflow to run) has to be given.
        Workflow_run uuid is auto-generated when the object is created.
        """
        self.uuid = generate_uuid()
        self.workflow = workflow_uuid
        self.run_platform = 'SBG'
        self.sbg_task_id = ''
        self.sbg_mounted_volume_ids = []
        self.sbg_import_ids = []
        self.sbg_export_ids = []
        self.award = '1U01CA200059-01'
        self.lab = '4dn-dcic-lab'
        self.input_files = metadata_input
        self.parameters = metadata_parameters

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
    '''
    class __metaclass__(type):
        def __iter__(self):
            for attr in dir(WorkflowRunMetadata):
                if not attr.startswith("__"):
                    yield(attr)        
    '''

class SBGWorkflowRun(object): ## one object per workflow run

    base_url = "https://api.sbgenomics.com/v2"

    def __init__(self, token, project_id, app_name):
        self.token=token
        self.header={ "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
        self.project_id=project_id
        self.app_name = app_name
        self.volume_list=[]    ## list of volumes mounted for the current run. We keep the information here so that they can be deleted later
        self.import_id_list=[]    ## list of import ids for the files imported for the current run.
        self.task_id=''    ## task_id for the current workflow run. It will be assigned after draft task is successfully created. We keep the information here, so we can re-run the task if it fails and also for the sanity check - so that we only run tasks that we created.
        self.task_input=None    ## SBGTaskInput object


    def sbg2workflowrun (self, workflow_uuid, metadata_input=[], metadata_parameters=[]):
        wr = WorkflowRunMetadata(workflow_uuid, metadata_input, metadata_parameters)
        wr.title = self.app_name + " run " + str(datetime.datetime.now())
        wr.sbg_task_id=self.task_id
        wr.sbg_mounted_volume_ids=[]
        for x in self.volume_list:
          wr.sbg_mounted_volume_ids.append(x.id)
        wr.sbg_import_ids=self.import_id_list
        return (wr.__dict__)


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
            "description" : "some volume",
            "service" : {
                 "type": "s3",
                 "bucket": bucket_name,
                 "prefix": bucket_object_prefix, ## prefix of objects, this causs some confusion later when referring to the mounted file, because you have to exclude the prefix part, so just keep it as ''. 
                 "credentials": {
                     "access_key_id": public_key, ## public access key for our s3 bucket
                     "secret_access_key": secret_key    ## secret access key for our s3 bucket
                 },
                 "properties": {
                     "sse_algorithm": "AES256"
                 }
            },
            "access_mode" : access_mode    ## either 'rw' or 'ro'.
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
             sbgtaskinput.add_inputparam("fastq", "type")
    
             return(sbgtaskinput)
    
        except Exception as e:
             print(e)
             print('Error creating a task payload')
             raise e 


    

## function that grabs SBG token from a designated S3 bucket
def get_sbg_token (s3):
    try:
        s3.Bucket(bucket_for_token).download_file(object_for_token, '/tmp/'+ object_for_token)    ## lambda doesn't have write access to every place, so use /tmp/.
        with open('/tmp/' + object_for_token, 'r') as f:    
            token = f.readline().rstrip()
        return token
    except Exception as e:
        print(e)
        print('Error getting token from S3.')
        raise e


def get_keypairs_file (s3):
    try:
        file_location = '/tmp/'+ object_for_keypairs
        s3.Bucket(bucket_for_keypairs).download_file(object_for_keypairs, file_location)    ## lambda doesn't have write access to every place, so use /tmp/.
        return file_location

    except Exception as e:
        print(e)
        print('Error getting token from S3.')
        raise e


def get_access_key (s3):
    try:
        s3.Bucket(bucket_for_token).download_file(object_for_access_key, '/tmp/'+ object_for_access_key)
        with open('/tmp/' + object_for_access_key, 'r') as f:
            access_key = f.read().splitlines()
        return access_key

    except Exception as e:
        print(e)
        print('Error getting access key from S3.')
        raise e

## This function is TEMPORARY - most of the jobs will run for more than the lifespan of this lambda function.
## Use it for test purpose for a tiny input file.
def check_task (token, task_id):
        url = sbg_base_url + "/tasks/" + task_id
        headers = {'X-SBG-Auth-Token': token,
                             'Content-Type': 'application/json'}

        data = {}
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
        return(response.json().get('id'))
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
        return check_export(token, export_id).get('state')
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
         file_type_list = ['outputs']    ## transfer only output files
    else:
         file_type_list = ['inputs', 'outputs']    ## transfer both input and output files

    # input/output files
    # export files to s3, add to file metadata json, add to workflow_run dictionary
    for file_type in file_type_list:
        if file_type=='inputs':
             workflow_run_file_type='input_files'
        else:
             workflow_run_file_type='output_files'
             
        for k,v in report_dict.get(file_type).iteritems():
            if isinstance(v, dict) and v.get('class')=='File':     ## This is a file
                 sbg_filename = v['name']
                 uuid = processed_files_report[sbg_filename]['uuid']
                 workflow_run[workflow_run_file_type].append({'workflow_argument_name':k, 'value':uuid})

            elif isinstance(v, list):
                 for v_el in v:
                        if isinstance(v_el, dict) and v_el.get('class')=='File':    ## This is a file (v is an array of files)
                             sbg_filename = v['name']
                             uuid = processed_files_report[sbg_filename]['uuid']
                             workflow_run[workflow_run_file_type].append({'workflow_argument_name':k, 'value':uuid})

    # parameters
    # add to workflow_run dictionary
    # assuming that parameters in the sbg report are either a single value or an array of single values.
    for k, v in report_dict.get('inputs').iteritems():
         if not isinstance(v, dict) and not isinstance(v, list):
                workflow_run['parameters'].append({'workflow_argument_name':k, 'value':v})
         if isinstance(v, list):
                for v_el in v:
                     if not isinstance(v_el, dict):
                            workflow_run['parameters'].append({'workflow_argument_name':k, 'value':v_el})

    return (workflow_run)    ## later change to actually 'updating metadata'



# Initiate exporting all output files to S3 and returns an array of {filename, export_id} dictionary
# export_id should be used to track export status.
def export_all_output_files(token, sbg_volume, sbg_run_detail_resp):

    export_report = []

    workflow_run_file_type='output_files'
    file_type = 'outputs'

    # export all output files to s3
    for k, v in sbg_run_detail_resp.get(file_type).iteritems():
        if isinstance(v, dict) and v.get('class')=='File':     ## This is a file
             sbg_file_id = v['path'].encode('utf8')
             sbg_filename = v['name'].encode('utf8')
             export_id = export_to_volume (token, sbg_file_id, sbg_volume.id, sbg_filename)
             export_report.append( {"filename":sbg_filename, "export_id":export_id } )


        elif isinstance(v, list):
             for v_el in v:
                    if isinstance(v_el, dict) and v_el.get('class')=='File':    ## This is a file (v is an array of files)
                         sbg_file_id = v['path'].encode('utf8')
                         sbg_filename = v['name'].encode('utf8')
                         export_id = export_to_volume (token, sbg_file_id, sbg_volume.id, sbg_filename)
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

        fill_report[filename]={"export_id":export_id, "status":status, "accession":accession, "uuid":uuid}

        # create a meta data file object
        metadata= {
            "accession": accession,
            "filename": 's3://' + bucket_name + '/' + filename,
            "notes": "sample dcic notes",
            "lab": "4dn-dcic-lab",
            "submitted_by": "admin@admin.com",
            "award": "1U01CA200059-01",
            "file_format": "other",
            #"experiments":["4DNEX067APT1"],
            "uuid": uuid,
            "status": "export " + status
        }

        processed_files.append(metadata)

    return ({"metadata":processed_files,"report": fill_report })




## function that returns a requests response in a nicely indented json format.
def format_response (response):
    return json.dumps(json.loads(response.text), indent=4)


def post_to_metadata(keypairs_file, post_item, schema_name):

    assert os.path.isfile(keypairs_file)

    try:
        key = fdnDCIC.FDN_Key(keypairs_file, "default")
    except Exception as e:
        print(e)
        print("key error")
        raise e

    try:
        connection = fdnDCIC.FDN_Connection(key)
    except Exception as e:
        print(e)
        print("connection error")
        raise e

    try:
        response = fdnDCIC.new_FDN(connection, schema_name, post_item)
    except Exception as e:
        print(e)
        print("post error")
        raise e

    return(response)


@app.route("/")
def index():
    pass


@app.route("/run", methods=['POST'])
def RUN():

        event = app.current_request.json_body

        input_file_list = event.get('input_files')
        app_name = event.get('app_name').encode('utf8')
        parameter_dict = event.get('parameters')
        workflow_uuid = event.get('workflow_uuid').encode('utf8')  
        '''
        workflow_uuid : for now, pass this on. Later we can add a code to automatically retrieve this from app_name (or vice versa).
        Note multiple workflow_uuids can be available for an app_name (different versions of the same app could have a different uuid)
        '''

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

        ## get key json file (Jeremy: modify this later)
        try:
                metadata_keypairs_file = get_keypairs_file(s3)

        except Exception as e:
                print(e)
                print('Error getting keypairs file from bucket {}.'.format(bucket))
                raise e


        ## create a sbg workflow run object to use
        sbg = SBGWorkflowRun(token, sbg_project_id, app_name)

        ## mount multiple input files to SBG S3 and
        ## create a SBGTaskInput object that contains multiple files and given parameters
        print(json.dumps(parameter_dict))
        task_input = SBGTaskInput(sbg_project_id, app_name, parameter_dict)
        print(task_input.__dict__)

        ## initalize metadata parameters and input file array
        metadata_parameters=[]
        for k,v in parameter_dict.iteritems():
            if isinstance(k, (str, unicode)):
                k = k.encode('utf-8')
            if isinstance(v, (str, unicode)):
                v = v.encode('utf-8')
            else:
                v = str(v)
            metadata_parameters.append( { "workflow_argument_name": k, "value": v } )
        print(metadata_parameters)
        metadata_input= []

        for e in input_file_list:

                print(e)
                bucket = e.get('bucket_name').encode('utf8')
                key = e.get('object_key').encode('utf8')
                workflow_argument = e.get('workflow_argument_name').encode('utf8')
                key_uuid = e.get('uuid').encode('utf8')
        
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
                        sbg_create_volume_response = sbg.create_volumes (sbg_volume, bucket, public_key=access_key[0], secret_key=access_key[1], bucket_object_prefix = key_uuid + '/' )
                        print(sbg_create_volume_response)    ## DEBUGGING
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
                        metadata_input.append( { "workflow_argument_name": workflow_argument, "value": key_uuid })
                
                except Exception as e:
                        print(e)
                        print('Error mounting/importing the file to SBG') 
                        raise e 

        # run a validatefiles task 
        try:
                #task_data = sbg.create_data_payload_validatefiles( sbg_check_import_response)
                print(json.dumps(task_input.__dict__, indent=4))
                create_task_response = sbg.create_task( task_input )
                run_response = sbg.run_task()

        except Exception as e:
                print(e)
                print('Error running a task')
                raise e
        

        # check task
        try:
                check_task_response = sbg.check_task()

        except Exception as e:
                print(e)
                print('Error running a task')
                raise e
        
        # post to metadata
        try:
                wr = sbg.sbg2workflowrun(workflow_uuid, metadata_input, metadata_parameters)
                print(json.dumps(wr))
                workflow_post_resp = post_to_metadata(metadata_keypairs_file, wr, "workflow_run_sbg")

                return( { "sbg_task": check_task_response, "metadata_object": workflow_post_resp} )

        except Exception as e:
                print(e)
                print('Error posting to metadata')
                raise e


        # for debugging
        try:
                print(json.dumps(sbg.__dict__))
        except Exception as e:
                print(e)
                print("Error printing the SBGWorkflowRun object.")
                raise e




@app.route("/export", methods=['POST'])
def EXPORT():
        event = app.current_request.json_body

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
                print("got token and access_key")

        except Exception as e:
                print(e)
                print('Error getting token and access key from bucket {}.'.format(bucket))
                raise e
        

        # create an sbg object
        sbg = SBGWorkflowRun(token, sbg_project_id)

        # check task 
        try:
                check_task_response = check_task (token, task_id)
                print("got check_task response")
                print(check_task_response)

        except Exception as e:
                print(e)
                print('Error running a task')
                raise e
        

        run_status = check_task_response.get('status') 
        print(run_status)

        if run_status == 'COMPLETED' or run_status == 'FAILED':

            ## mount the output bucket (silent if already mounted)
            try:
                 sbg_volume= SBGVolume() 
                 print("created an output volume id")
                 sbg_create_volume_response = sbg.create_volumes (sbg_volume, bucket, public_key=access_key[0], secret_key=access_key[1])
                 print("created an output volume")

            except Exception as e:
                 print(e)
                 print('Error mounting output bucket to SBG') 
                 raise e


            ## initiate output file export and fill in metadata
            try:
                 export_report = export_all_output_files(token, sbg_volume, check_task_response)    #array of {filename, export_id}
                 time.sleep(10)    # give some time so that small files can be finished exporting before checking export status.
                 processed_files_result = fill_processed_files(token, export_report, bucket)
                 print(str(processed_files_result))    ## DEBUGGING
                 metadata_processed_files = processed_files_result['metadata']
                 print(str(metadata_processed_files))    ## DEBUGGING
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


@app.route("/finalize", methods=['POST'])
def FINALIZE():
        event = app.current_request.json_body

        # Get the object from the event and show its content type
        task_id = event['task_id'].encode('utf8')     
        export_id_list = event['export_id_list']
        output_handling_type = event['output_handler'].encode('utf8')

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
                print("got token and access_key")

        except Exception as e:
                print(e)
                print('Error getting token and access key from bucket {}.'.format(bucket))
                raise e
        

        # create an sbg object
        sbg = SBGWorkflowRun(token, sbg_project_id)

        # check task 
        try:
                overall_export_status = ''
                for export_id in export_id_list:
                    export_status = check_export_status (token, export_id)
                    if export_status == "FAILED":
                        overall_export_status = "FAILED"
                        break
                    elif export_status != "COMPLETED":
                        overall_export_status = 'PENDING'
                if overall_export_status == '':
                    overall_export_status = 'COMPLETED'

                if overall_export_status == 'PENDING' or overall_export_status == 'FAILED':
                    return({"status": overall_export_status})

        except Exception as e:
                print(e)
                print('Error getting export status')
                raise e

        ## other things
        #     1. update workflow metadata
        #     2. either update file metadata or parse file and get qc metric



if __name__ == "__main__":
     print ("haha")

