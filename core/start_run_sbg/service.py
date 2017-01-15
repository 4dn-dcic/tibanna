# -*- coding: utf-8 -*-

import boto3
from core import utils
import json
import random

s3 = boto3.resource('s3')


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
    s3_keys = event.get('s3_keys')
    if not s3_keys:
        s3_keys = utils.get_s3_keys()

    sbg = utils.create_sbg_workflow(app_name)

    # mount all files to sbg
    mounts3_tasks = [mount_on_sbg(infile, s3_keys, sbg) for infile in input_file_list]

    # let's not pass keys in plain text parameters
    return {"import_ids": mounts3_tasks,
            "input_file_args": input_file_list,
            "workflow": sbg.as_dict(),
            "workflow_uuid": workflow_uuid,
            "parameter_dict": parameter_dict}

    '''
    for sbg_import_id in mounts3_tasks:
        sbg_check_import_response = sbg.get_details_of_import(sbg_import_id)

        ## add to task input
        try:
            sbg_file_name = sbg_check_import_response.get('result').get('name')
            sbg_file_id = sbg_check_import_response.get('result').get('id')
            task_input.add_inputfile(sbg_file_name, sbg_file_id, workflow_argument )
            metadata_input.append( { "workflow_argument_name": workflow_argument, "value": key_uuid })

        except Exception as e:
            print(e)
            print('Error mounting/importing the file to SBG')
            raise e

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
def mount_on_sbg(input_file, s3_keys, sbg):
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
        sbg_volume = utils.create_sbg_volume_details()
        sbg.create_volumes(sbg_volume, bucket,
                           public_key=s3_keys['key'],
                           secret_key=s3_keys['secret'],
                           bucket_object_prefix=key_uuid + '/')
        return sbg.import_volume_content(sbg_volume, key)
    except Exception as e:
        print("error importing to SBG")
        raise(e)

'''
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
'''


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

