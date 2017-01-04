# -*- coding: utf-8 -*-

import boto3
from core import utils
import json
import random
import requests

s3 = boto3.resource('s3')

###########################
# Config
###########################
SBG_PROJECT_ID = "4dn-dcic/dev"


def handler(event, context):
    '''
    this is generic function to run sbg workflow
    based on the data passed in

    workflow_uuid : for now, pass this on. Later we can add a code to automatically retrieve this from app_name.
    Note multiple workflow_uuids can be available for an app_name
    (different versions of the same app could have a different uuid)
    '''
    # get incomming data
    input_file_list = event.get('input_files')
    app_name = event.get('app_name').encode('utf8')
    parameter_dict = event.get('parameters')
    workflow_uuid = event.get('workflow_uuid').encode('utf8')

    # get necessary tokens
    # access_key = utils.get_access_keys()
    s3_key = utils.get_s3_keys()

    sbg = create_sbg_workflow(app_name)

    # create Task for workflow run later
    task_input = SBGTaskInput(SBG_PROJECT_ID, app_name, parameter_dict)

    # initalize metadata parameters and input file array
    metadata_parameters = []
    for k, v in parameter_dict.iteritems():
        if isinstance(k, (str, unicode)):
            k = k.encode('utf-8')
            if isinstance(v, (str, unicode)):
                v = v.encode('utf-8')
            else:
                v = str(v)
                metadata_parameters.append({"workflow_argument_name": k, "value": v})
                print(metadata_parameters)
                metadata_input = []

    # mount all files to sbg
    mounts3_tasks = [mount_on_sbg(infile) for infile in input_file_list]

    for sbg_import_id in mounts3_tasks:
        sbg_check_import_response = sbg.get_details_of_import(sbg_import_id)

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

    '''
    # run a validatefiles task
    try:
        # task_data = sbg.create_data_payload_validatefiles(sbg_check_import_response)
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
    '''


##########################
# Extra Functions
#################


def create_sbg_workflow(app_name):
    # get necessary tokens
    token = utils.get_sbg_keys()

    # create data for sbg workflow run
    # create a sbg workflow run object to use
    return SBGWorkflowRun(token, SBG_PROJECT_ID, app_name)


def mount_on_sbg(input_file, s3_key, sbg):
    # get important info from input_file json
    bucket = input_file.get('bucket_name').encode('utf8')
    key = input_file.get('object_key').encode('utf8')
    key_uuid = input_file.get('uuid').encode('utf8')

    # check the bucket and key exists
    try:
        s3.Object(bucket, '%s/%s' % (key_uuid, key)).load()
    except Exception as e:
        print(e)
        print('ERROR: Object {} in bucket {} not found.'.format(key, bucket))
        raise e

    # mount the bucket and import the file
    try:
        sbg_volume = SBGVolume()
        sbg.create_volumes(sbg_volume, bucket,
                           public_key=s3_key['key'],
                           secret_key=s3_key['secret'],
                           bucket_object_prefix=key_uuid + '/')
        return sbg.import_volume_content(sbg_volume, key)
    except Exception as e:
        print("error importing to SBG")
        raise(e)


class SBGVolume(object):
    prefix = '4dn_s3'
    account = '4dn-labor'

    def __init__(self, volume_suffix=None, volume_id=None):

        if volume_id is not None:
            self.id = volume_id
            self.name = self.id.split('/')[1]

        else:
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


    def __init__(self, workflow_uuid, metadata_input=[], metadata_parameters=[], task_id=None, import_ids=None, export_ids=None, mounted_volume_ids=None):
        """Class for WorkflowRun that matches the 4DN Metadata schema
        Workflow_uuid (uuid of the workflow to run) has to be given.
        Workflow_run uuid is auto-generated when the object is created.
        """
        self.uuid = generate_uuid()
        self.workflow = workflow_uuid
        self.run_platform = 'SBG'   # for now we use only SBG - we can change it later as we add tibanna
        if task_id is None:
            self.sbg_task_id = ''
        else:
            self.sbg_task_id = task_id

        if mounted_volume_ids is None:
            self.sbg_mounted_volume_ids = []
        else:
            self.sbg_mounted_volume_ids = mounted_volume_ids
        if import_ids is None:
            self.sbg_import_ids = []
        else:
            self.sbg_import_ids = import_ids
        if export_ids is None:
            self.sbg_export_ids = []
        else:
            self.sbg_export_ids = export_ids
        self.input_files = metadata_input
        self.parameters = metadata_parameters
        self.output_files = []
        self.award = '1U01CA200059-01'
        self.lab = '4dn-dcic-lab'

    def append_outputfile(outjson):
        self.output_files.append(outjson)

    def append_volumes(sbg_volume):
        self.sbg_mounted_volume_ids.append(sbg_volume.id)

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)


class FileProcessedMetadata(object):


    def __init__(self, uuid, accession, filename, status, workflow_run_uuid=None):
        self.uuid = uuid
        self.accession = accession
        self.filename = filename
        self.file_format = "other"  # we will deal with this later
        self.status = status 
        if workflow_run_uuid is not None:
            self.workflow_run = workflow_run_uuid
        # default assign to 4dn-dcic - later change to input file submitter
        self.notes = "sample dcic notes"
        self.lab= "4dn-dcic-lab"
        self.submitted_by= "4dndcic@gmail.com"
        self.award= "1U01CA200059-01"

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)


class SBGWorkflowRun(object): ## one object per workflow run

    base_url = "https://api.sbgenomics.com/v2"

    def __init__(self, token, project_id, app_name, task_id='', import_ids=[], mounted_volume_ids=[], export_ids=[]):
        self.token=token
        self.header = { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
        self.project_id = project_id
        self.app_name = app_name
        self.volume_list = [SBGVolume(None, volume_id=id) for id in mounted_volume_ids]    ## list of volumes mounted for the current run. We keep the information here so that they can be deleted later
        self.import_id_list = import_ids    ## list of import ids for the files imported for the current run.
        self.task_id=task_id    ## task_id for the current workflow run. It will be assigned after draft task is successfully created. We keep the information here, so we can re-run the task if it fails and also for the sanity check - so that we only run tasks that we created.
        self.task_input = None    ## SBGTaskInput object
        self.export_report = [{"filename": '', "export_id": id} for id in export_ids]
        self.export_id_list = export_ids


    def sbg2workflowrun (self, workflow_uuid, metadata_input=[], metadata_parameters=[]):
        wr = WorkflowRunMetadata(workflow_uuid, metadata_input, metadata_parameters)
        wr.title = self.app_name + " run " + str(datetime.datetime.now())
        wr.sbg_task_id = self.task_id
        wr.sbg_mounted_volume_ids = []
        for x in self.volume_list:
          wr.sbg_mounted_volume_ids.append(x.id)
        wr.sbg_import_ids=self.import_id_list
        return (wr.__dict__)


    ## function that creates a mounted volume on SBG
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


    # Initiate exporting all output files to S3 and returns an array of {filename, export_id} dictionary
    # export_id should be used to track export status.
    def export_all_output_files(self, sbg_volume, sbg_run_detail_resp):
    
        self.export_report = []
        self.export_id_list = []

        workflow_run_file_type='output_files'
    
        # export all output files to s3
        for k, v in sbg_run_detail_resp.get('outputs').iteritems():
            if isinstance(v, dict) and v.get('class')=='File':     ## This is a file
                 sbg_file_id = v['path'].encode('utf8')
                 sbg_filename = v['name'].encode('utf8')
                 export_id = self.export_to_volume (sbg_file_id, sbg_volume, sbg_filename)
                 self.export_report.append( {"filename":sbg_filename, "export_id":export_id } )
                 self.export_id_list.append(export_id)
    
            elif isinstance(v, list):
                 for v_el in v:
                        if isinstance(v_el, dict) and v_el.get('class')=='File':    ## This is a file (v is an array of files)
                             sbg_file_id = v['path'].encode('utf8')
                             sbg_filename = v['name'].encode('utf8')
                             export_id = self.export_to_volume (sbg_file_id, sbg_volume, sbg_filename)
                             self.export_report.append( {"filename":sbg_filename, "export_id":export_id } )
                             self.export_id_list.append(export_id)

        print(self.export_report)  # debugging


    def fill_processed_file_metadata(self, bucket_name, workflow_run_uuid):
    
        processed_files=[]
        fill_report={}
    
        for file in self.export_report:
            filename = file['filename']
            export_id = file['export_id']
            status = self.get_export_status(export_id)
    
            accession=generate_rand_accession()
            uuid=generate_uuid()
    
            fill_report[filename] = {"export_id": export_id, "status": status, "accession": accession, "uuid": uuid}
    
            # create a meta data file object
            # metadata = FileProcessedMetadata(uuid, accession, filename, "uploading", workflow_run_uuid)  # if I add workflow_run_uuis, I get an error message like : '577c2684-49e5-4c33-afab-9ec90d65faf3' is not of type 'WorkflowRun'
            metadata = FileProcessedMetadata(uuid, accession, filename, "uploading")
            print(metadata.__dict__)
            processed_files.append(metadata.__dict__)
    
        return ({"metadata": processed_files,"report": fill_report })
    

    # This function exports a file on SBG to a mounted output bucket and returns export_id
    def export_to_volume (self, source_file_id, sbg_volume, dest_filename):

        if sbg_volume not in self.volume_list:
            print("Error: the specified volume doesn't exist in the current workflow run.")    
            sys.exit()

        export_url = self.base_url + "/storage/exports/"
        data = {
            "source": {
                "file": source_file_id
            },
            "destination": {
                "volume": sbg_volume.id,
                "location": dest_filename
            }
        }
        print("export data = {}".format(json.dumps(data)))
        response = requests.post(export_url, headers=self.header, data=json.dumps(data))
        print(response.json())
        
        if response.json().has_key('id'):
            return(response.json().get('id'))
            export_id = response.json().get('id')
            if export_id not in self.export_id_list:
                self.export_id_list.append(export_id)
            return(export_id)

        else:
            print("Export error")
            print(response)
            sys.exit()


    def get_export_status (self, export_id):
        result = self.check_export(export_id)
        print(result)
        if result.has_key('state'):
            return self.check_export(export_id).get('state')
        else:
            return None

    
    def check_export (self, export_id):
        export_url = self.base_url + "/storage/exports/" + export_id
        data = { "export_id" : export_id }
        response = requests.get(export_url, headers=self.header, data=json.dumps(data))
        return(response.json())


    def delete_volumes(self):
        response_all=[]
        for sbg_volume in self.volume_list:
            url = self.base_url + "/storage/volumes/" + sbg_volume.id
            response = requests.delete(url, headers=self.header)
            response_all.append(response)
        self.volume_list=[]
        return({"responses": response_all})

    def delete_imported_files(self):
        response_all=[]
        for import_id in self.import_id_list:
            import_detail = self.get_details_of_import(import_id)
            imported_file_id = import_detail.get('result').get('id')
            url = self.base_url + "/storage/files/" + imported_file_id
            response = requests.delete(url, headers=self.header)
            response_all.append(response)
        self.import_id_list=[]
        return({"responses": response_all})


    def delete_exported_files(self):
        response_all=[]
        for export_id in self.export_id_list:
            export_detail = self.check_export(export_id)
            exported_file_id = export_detail.get('source').get('file')
            url = self.base_url + "/storage/files/" + exported_file_id
            response = requests.delete(url, headers=self.header)
            response_all.append(response)
        return({"responses": response_all})


## function that grabs SBG token from a designated S3 bucket
def get_sbg_token (s3):
    try:
        s3.Bucket(bucket_for_token).download_file(object_for_token, '/tmp/'+ object_for_token)    # lambda doesn't have write access to every place, so use /tmp/.
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
        s3.Bucket(bucket_for_keypairs).download_file(object_for_keypairs, file_location)    # lambda doesn't have write access to every place, so use /tmp/.
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





def generate_uuid ():
    rand_uuid_start=''
    rand_uuid_end=''
    for i in xrange(8):
        r=random.choice('abcdef1234567890')
        rand_uuid_start += r
    for i in xrange(12):
        r2=random.choice('abcdef1234567890')
        rand_uuid_end += r2
    uuid=rand_uuid_start + "-49e5-4c33-afab-" + rand_uuid_end
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
def get_output_patch_for_workflow_run(sbg_run_detail_resp, processed_files_report, sbg_volume, wr):

    outputfiles=[]
    processed_files = []    
    export_id_list = []

    report_dict = sbg_run_detail_resp

    # input/output files
    # export files to s3, add to file metadata json, add to workflow_run dictionary
    for k,v in report_dict.get('outputs').iteritems():
        if isinstance(v, dict) and v.get('class')=='File':     ## This is a file
             sbg_filename = v['name']
             uuid = processed_files_report[sbg_filename]['uuid']
             export_id = processed_files_report[sbg_filename]['export_id']
             outputfiles.append({'workflow_argument_name':k, 'value':uuid})
             export_id_list.append(export_id)

        elif isinstance(v, list):
             for v_el in v:
                    if isinstance(v_el, dict) and v_el.get('class')=='File':    ## This is a file (v is an array of files)
                         sbg_filename = v['name']
                         uuid = processed_files_report[sbg_filename]['uuid']
                         export_id = processed_files_report[sbg_filename]['export_id']
                         outputfiles.append({'workflow_argument_name':k, 'value':uuid})
                         export_id_list.append(export_id)

    wr.sbg_mounted_volume_ids.append(sbg_volume.id)
    return ({"output_files": outputfiles, "run_status": "output_files_transferring", "sbg_export_ids": export_id_list, "sbg_mounted_volume_ids": wr.sbg_mounted_volume_ids})



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





def get_metadata(keypairs_file, schema_name=None, schema_class_name=None, uuid=None):

    assert os.path.isfile(str(keypairs_file))

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
        if schema_name is not None:
            response = fdnDCIC.get_FDN(schema_name, connection)
            return(response)
        if schema_class_name is not None:
            response = fdnDCIC.get_FDN("search/?type=" + schema_class_name, connection)
            return(response)
        if uuid is not None:
            response = fdnDCIC.get_FDN(uuid, connection)
            return(response)

    except Exception as e:
        print(e)
        print("get error")
        raise e


def patch_to_metadata(keypairs_file, patch_item, schema_class_name=None, accession=None, uuid=None):

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
        if(schema_class_name is not None):
            resp = fdnDCIC.get_FDN("/search/?type=" + schema_class_name, connection)
            items_uuids = [i['uuid'] for i in resp['@graph']]
        elif(accession is not None):
            resp = fdnDCIC.get_FDN("/" + accession, connection)
            item_uuid = resp.get('uuid')
            items_uuids = [item_uuid]
        elif(uuid is not None):
            items_uuids = [uuid]
        else:
            items_uuids = []

    except Exception as e:
        print(e)
        print("get error")
        raise e

    try:
        for item_uuid in items_uuids:
            response = fdnDCIC.patch_FDN(item_uuid, connection, patch_item)
            return(response)

    except Exception as e:
        print(e)
        print("get error")
        raise e

