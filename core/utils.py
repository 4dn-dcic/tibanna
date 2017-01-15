from __future__ import print_function

import json
import boto3
import os
import requests
import random


###########################
# Config
###########################
SBG_PROJECT_ID = "4dn-dcic/dev"
s3 = boto3.client('s3')
SYS_BUCKET = 'elasticbeanstalk-encoded-4dn-system'
keyfile_name = 'illnevertell'


class SBGAPI(object):
    base_url = "https://api.sbgenomics.com/v2"

    def __init__(self, token=None):
        if not token:
            token = get_sbg_keys()
        self.token = token
        self.header = {"X-SBG-Auth-Token": token, "Content-type": "application/json"}

    def _get(self, partial_url, data):
        url = self.base_url + partial_url
        return requests.get(url, headers=self.header, data=json.dumps(data))


def get_access_keys():
    return get_key(keyfile_name)['default']


def get_sbg_keys():
    return get_key('sbgkey')


def get_s3_keys():
    return get_key('sbgs3key')


def get_key(keyfile_name='illnevertell'):
    # Share secret encrypted S3 File
    response = s3.get_object(Bucket=SYS_BUCKET,
                             Key=keyfile_name,
                             SSECustomerKey=os.environ.get("SECRET"),
                             SSECustomerAlgorithm='AES256')
    akey = response['Body'].read()
    try:
        return json.loads(akey)
    except ValueError:
        # maybe its not json after all
        return akey


def to_sbg_workflow_args(parameter_dict):
    metadata_parameters = []
    metadata_input = []
    for k, v in parameter_dict.iteritems():
        # we need this to be an integer if it really is, else a string
        try:
            v = int(v)
        except ValueError:
            v = str(v)

        metadata_parameters.append({"workflow_argument_name": k, "value": v})

    return (metadata_parameters, metadata_input)


def create_sbg_volume_details(volume_suffix=None, volume_id=None):
    prefix = '4dn_s3'
    account = '4dn-labor'
    id = ''
    name = ''
    if volume_id is not None:
        id = volume_id
        name = id.split('/')[1]

    else:
        if volume_suffix is None:
            volume_suffix = ''
            for i in xrange(8):
                r = random.choice('abcdefghijklmnopqrstuvwxyz1234567890')
                volume_suffix += r

        name = prefix + volume_suffix  # name of the volume to be mounted on sbg.
        id = account + '/' + name    # ID of the volume to be mounted on sbg.

    return {'id': id, 'name': name}


def create_sbg_workflow(app_name, task_id='', task_input=None, token=None,
                        project_id=None, import_id_list=None, mounted_volume_ids=None,
                        export_id_list=None, **kwargs):
    '''
    helper function to be used to create object from serialized json dictionary
    '''

    # get necessary tokens
    if not token:
        token = get_sbg_keys()

    if not project_id:
        project_id = SBG_PROJECT_ID

    if not mounted_volume_ids and kwargs.get('volume_list'):
        mounted_volume_ids = [v['id'] for v in kwargs.get('volume_list')]

    task_input_class = None
    if task_input:
        task_input_class = SBGTaskInput(task_input['name'],
                                        project=task_input['project'],
                                        inputs=task_input['inputs'])
    # create data for sbg workflow run
    # create a sbg workflow run object to use
    wfrun = SBGWorkflowRun(token, project_id, app_name, task_id, task_input_class, import_id_list,
                           mounted_volume_ids, export_id_list)
    return wfrun


class SBGWorkflowRun(object):
    '''
    This class is mainly used to keep state information about our workflow run to be
    passed between the various lambda functions that orchestrate our workflow execution
    on sbg.
    '''

    base_url = "https://api.sbgenomics.com/v2"

    def __init__(self, token, project_id, app_name, task_id='', task_input=None,
                 import_id_list=None, mounted_volume_ids=None, export_id_list=None,
                 header=None):

        # list of import ids for the files imported for the current run.
        self.import_id_list = [] if import_id_list is None else import_id_list
        mounted_volume_ids = [] if mounted_volume_ids is None else mounted_volume_ids
        self.export_id_list = [] if export_id_list is None else export_id_list
        if not header:
            self.header = {"X-SBG-Auth-Token": token, "Content-type": "application/json"}
        else:
            self.header = header
        self.project_id = project_id
        self.app_name = app_name
        # list of volumes mounted for the current run. Helpful for deleting vols later
        self.volume_list = [create_sbg_volume_details(None, volume_id=id) for id in mounted_volume_ids]

        '''
        task_id for the current workflow run. It will be assigned after draft task
        is successfully created. We keep the information here, so we can re-run the
        task if it fails and also for the sanity check - so that we only run tasks that we created.
        '''
        self.task_id = task_id
        self.task_input = task_input  # SBGTaskInput object
        if task_input:
            # ensure task_input matches this workflow
            assert task_input.name == self.app_name
            assert task_input.project == self.project_id

        self.export_report = [{"filename": '', "export_id": id} for id in self.export_id_list]

    def as_dict(self):
        cleaned_workflow = self.__dict__.copy()
        cleaned_workflow.pop('header')
        ti = cleaned_workflow.get('task_input')
        if ti:
            cleaned_workflow['task_input'] = ti.as_dict()
        return cleaned_workflow

    def sbg2workflowrun(self, workflow_uuid, metadata_input=[], metadata_parameters=[]):
        '''
        wr = WorkflowRunMetadata(workflow_uuid, metadata_input, metadata_parameters)
        wr.title = self.app_name + " run " + str(datetime.datetime.now())
        wr.sbg_task_id = self.task_id
        wr.sbg_mounted_volume_ids = []
        for x in self.volume_list:
          wr.sbg_mounted_volume_ids.append(x)
        wr.sbg_import_ids=self.import_id_list
        return (wr.__dict__)
        '''
        pass

    def create_volumes(self, sbg_volume, bucket_name, public_key,
                       secret_key, bucket_object_prefix='', access_mode='rw'):
        '''
        function that creates a mounted volume on SBG
        sbg_volume:
        bucket_name: name of bucket to mount
        public_key, secret_key: keys for S3 bucket
        bucket_object_prefix : for subdirectory inside the bucket, use subdirectory_name+'/'
        access_mode : 'ro' for readonly 'rw' for read and write
        '''

        volume_url = self.base_url + "/storage/volumes/"
        data = {
            "name": sbg_volume['name'],
            "description": "some volume",
            "service": {
                 "type": "s3",
                 "bucket": bucket_name,
                 "prefix": bucket_object_prefix,
                 "credentials": {
                     "access_key_id": public_key,  # public access key for our s3 bucket
                     "secret_access_key": secret_key   # secret access key for our s3 bucket
                 },
                 "properties": {
                     "sse_algorithm": "AES256"
                 }
            },
            "access_mode": access_mode  # either 'rw' or 'ro'.
        }

        try:
            response = requests.post(volume_url, headers=self.header, data=json.dumps(data))
            # update volume_list
            if sbg_volume not in self.volume_list:
                self.volume_list.append(sbg_volume)
            return(response.json())
        except Exception as e:
            print(e)
            print("volume creation error")
            raise e

    def import_volume_content(self, sbg_volume, object_key, dest_filename=None):
        '''
        function that initiations importing (mounting) an object on 4dn s3 to SBG s3
        source_filename : object key on 4dn s3
        dest_filename : filename-to-be on SBG s3 (default, to be the same as source_filename)
        return value : the newly imported (mounted) file's ID on SBG S3
        '''
        if sbg_volume not in self.volume_list:
            raise Exception("Error: the specified volume doesn't exist in the current workflow run.")

        source_filename = object_key
        if dest_filename is None:
            dest_filename = object_key
        import_url = self.base_url + "/storage/imports"
        data = {
            "source": {
                "volume": sbg_volume['id'],
                "location": source_filename
            },
            "destination": {
                "project": self.project_id,
                "name": dest_filename
            },
            "overwrite": True
        }
        response = requests.post(import_url, headers=self.header, data=json.dumps(data))

        import_id = response.json().get('id')
        if import_id:
            if import_id not in self.import_id_list:
                self.import_id_list.append(import_id)
            return(import_id)
        else:
            raise Exception("Error: import not successful.")

    def create_task(self, sbg_task_input):
        '''
        create a draft task on SBG, given a SBGTaskInput object
        '''
        url = self.base_url + "/tasks"
        data = sbg_task_input.__dict__
        resp = requests.post(url, headers=self.header, data=json.dumps(data))

        if 'id' in resp.json().keys():
            self.task_id = resp.json().get('id')
            self.task_input = sbg_task_input
            return resp.json()
        else:
            raise Exception("task not created succesfully, resp is %s" % resp.json())

    def run_task(self):
        '''
        run task on SBG
        A draft task must be created before running it
        '''
        if self.task_id is None:
            raise Exception("Error: no task_id available. Create a draft task first.")

        url = self.base_url + "/tasks/" + self.task_id + "/actions/run"
        data = self.task_input.__dict__
        resp = requests.post(url, headers=self.header, data=json.dumps(data))
        return(resp.json())  # return the run_task response

    def check_task(self):
        '''
        check status of task
        '''
        if self.task_id is None:
            raise Exception("Error: no task_id available. Create a draft task first.")

        url = self.base_url + "/tasks/" + self.task_id
        data = {}
        response = requests.get(url, headers=self.header, data=json.dumps(data))
        return response.json()

    def create_data_payload_validatefiles(import_response):
        '''
        example method for creating sbgtaskinput for validate app given the response body of
        import request in json format
        '''
        try:
            file_id = import_response.get('result').get('id')  # imported Id on SBG
            file_name = import_response.get('result').get('name')  # imported file name on SBG
            # app_name = "validate"

            sbgtaskinput = None  # SBGTaskInput(self.project_id, app_name)
            sbgtaskinput.add_inputfile(file_name, file_id, "input_file")
            sbgtaskinput.add_inputparam("fastq", "type")

            return(sbgtaskinput)
        except Exception as e:
            print(e)
            print('Error creating a task payload')
            raise e

    '''
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
                        ## This is a file (v is an array of files)
                        if isinstance(v_el, dict) and v_el.get('class')=='File':
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
            # metadata = FileProcessedMetadata(uuid, accession, filename,
            # "uploading", workflow_run_uuid)
            # if I add workflow_run_uuis, I get an error message like :
            # '577c2684-49e5-4c33-afab-9ec90d65faf3' is not of type 'WorkflowRun'

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
            url = self.base_url + "/storage/volumes/" + sbg_volume
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
    '''


class SBGTaskInput(object):
    def __init__(self, name, project, app='', inputs=None):
        self.name = name
        self.project = project
        if not app:
            self.app = project + "/" + name
        else:
            self.app = app
        if not inputs:
            self.inputs = {}
            for k, v in inputs.iteritems():
                if isinstance(k, (str, unicode)):
                    k = k.encode('utf-8')
                if isinstance(v, (str, unicode)):
                    v = v.encode('utf-8')
                self.add_inputparam(v, k)
        else:
            self.inputs = inputs

    def as_dict(self):
        return self.__dict__

    def add_input(self, new_input):
        self.inputs.update(new_input)

    def add_inputfile(self, filename, file_id, argument_name):
        new_input = {argument_name: {"class": "File", "name": filename, "path": file_id}}
        if self.check_validity_inputfile(new_input):
            self.add_input(new_input)
        else:
            raise Exception("Error: input format for SBGTaskInput not valid")

    def add_inputparam(self, param_name, argument_name):
        new_input = {argument_name: param_name}
        self.add_input(new_input)

    def check_validity_inputfile(self, ip):
        if (isinstance(ip, dict) and
                len(ip) == 1 and
                isinstance(ip.values()[0], dict) and
                'class' in ip.values()[0].keys() and
                'name' in ip.values()[0].keys() and
                'path' in ip.values()[0].keys()):
            return True
        else:
            return False


def current_env():
    return os.environ.get('ENV_NAME', 'test')
