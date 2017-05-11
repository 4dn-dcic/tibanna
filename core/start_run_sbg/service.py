# -*- coding: utf-8 -*-

import boto3
from core import sbg_utils, utils
from core.utils import s3Utils, Tibanna
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
    output_bucket = event.get('output_bucket')
    tibanna_settings = event.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env', '-'.join(output_bucket.split('-')[1:-1]))
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, s3_keys=event.get('s3_keys'), ff_keys=event.get('ff_keys'),
                      settings=tibanna_settings)

    # represents the SBG info we need
    sbg = sbg_utils.create_sbg_workflow(app_name, tibanna.sbg_keys)

    # represents the workflow metadata to be stored in fourfront
    parameters, _ = sbg_utils.to_sbg_workflow_args(parameter_dict, vals_as_string=True)

    # get argument format & type info from workflow
    workflow_info = sbg_utils.get_metadata(workflow_uuid, key=tibanna.ff_keys)
    # This dictionary has a key 'arguments' with a value { 'workflow_argument_name': ..., 'argument_type': ..., 'argument_format': ... }

    # get format-extension map
    try:
        fe_map = sbg_utils.get_metadata("profiles/file_processed.json", key=tibanna.ff_keys).get('file_format_file_extension')
    except Exception as e:
        print("Can't get format-extension map from file_processed schema. %s\n" % e)

    # create the ff_meta output info
    input_files = [{'workflow_argument_name': fil['workflow_argument_name'],
                    'value': fil['uuid']} for fil in input_file_list]

    # processed file metadata
    try:
        if workflow_info.has_key('arguments'):
            output_files = []
            pf_meta = []
            for arg in workflow_info.get('arguments'):
                if arg.has_key('argument_type') and arg['argument_type'] in ['Output processed file','Output report file','Output QC file']:
                    of = dict()
                    of['workflow_argument_name'] = arg.get('workflow_argument_name')
                    of['type'] = arg.get('argument_type')
                    if arg.has_key('argument_format'): # These are not processed files but report or QC files.
                        pf = sbg_utils.ProcessedFileMetadata(file_format=arg.get('argument_format'))
                        try:
                            resp = pf.post(key=tibanna.ff_keys)  # actually post processed file metadata here
                            resp = resp.get('@graph')[0]
                            of['upload_key'] = resp.get('upload_key')
                            of['value'] = resp.get('uuid')
                        except Exception as e:
                            print("Failed to post Processed file metadata. %s\n" % e)
                            print("resp" + str(resp) + "\n")
                        of['format'] = arg.get('argument_format')
                        of['extension'] = fe_map.get(arg.get('argument_format'))
                        pf_meta.append(pf)
                    output_files.append(of)

    except Exception as e:
        print("output_files = " + str(output_files) + "\n")
        print("Can't prepare output_files information. %s\n" % e)

    # create workflow run metadata
    try:
        ff_meta = sbg_utils.create_ffmeta(sbg, workflow_uuid, input_files, parameters,
                                          run_url=tibanna.settings.get('url', ''), output_files=output_files)
    except Exception as e:
        print("Can't create ffmeta. %s\n" % e)

    # store metadata so we know the run has started
    ff_meta.post(key=tibanna.ff_keys)

    # mount all input files to sbg this will also update sbg to store the import_ids
    _ = [mount_on_sbg(infile, tibanna.s3_keys, sbg) for infile in input_file_list]

    # create a link to the output directory as well
    if output_bucket:
        sbg_volume = sbg_utils.create_sbg_volume_details()
        res = sbg.create_volumes(sbg_volume, output_bucket,
                                 public_key=tibanna.s3_keys['key'],
                                 secret_key=tibanna.s3_keys['secret'])
        vol_id = res.get('id')
        if not vol_id:
            # we got an error
            raise Exception("Unable to mount output volume, error is %s " % res)
        sbg.output_volume_id = vol_id

    # let's not pass keys in plain text parameters
    return {"input_file_args": input_file_list,
            "workflow": sbg.as_dict(),
            "ff_meta": ff_meta.as_dict(),
            'pf_meta': [pf.as_dict() for pf in pf_meta],
            "_tibanna": tibanna.as_dict(),
            "parameter_dict": parameter_dict}


#################
# Extra Functions
#################

def mount_on_sbg(input_file, s3_keys, sbg):
    # get important info from input_file json
    bucket = input_file.get('bucket_name').encode('utf8')
    key = input_file.get('object_key').encode('utf8')
    key_uuid = input_file.get('uuid').encode('utf8')
    s3_key = "%s/%s" % (key_uuid, key)

    # check the bucket and key exists
    try:
        s3.Object(bucket, s3_key).load()
    except Exception as e:
        raise Exception('ERROR: Object {} in bucket {} not found\n{}.'.format(s3_key, bucket, e))

    # mount the bucket and import the file
    try:
        sbg_volume = sbg_utils.create_sbg_volume_details()
        sbg.create_volumes(sbg_volume, bucket,
                           public_key=s3_keys['key'],
                           secret_key=s3_keys['secret'],
                           bucket_object_prefix=key_uuid + '/')
        return sbg.import_volume_content(sbg_volume, key)
    except Exception as e:
        print("error importing to SBG")
        raise(e)


class FileProcessedMetadata(object):

    def __init__(self, uuid, accession, upload_key, status, workflow_run_uuid=None):
        self.uuid = uuid
        self.accession = accession
        self.upload_key = upload_key
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


# function that grabs SBG token from a designated S3 bucket
def get_sbg_token(s3):
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
             sbg_upload_key = v['name']
             uuid = processed_files_report[sbg_upload_key]['uuid']
             export_id = processed_files_report[sbg_upload_key]['export_id']
             outputfiles.append({'workflow_argument_name':k, 'value':uuid})
             export_id_list.append(export_id)

        elif isinstance(v, list):
             for v_el in v:
                    if isinstance(v_el, dict) and v_el.get('class')=='File':    ## This is a file (v is an array of files)
                         sbg_upload_key = v['name']
                         uuid = processed_files_report[sbg_upload_key]['uuid']
                         export_id = processed_files_report[sbg_upload_key]['export_id']
                         outputfiles.append({'workflow_argument_name':k, 'value':uuid})
                         export_id_list.append(export_id)

    wr.sbg_mounted_volume_ids.append(sbg_volume.id)
    return ({"output_files": outputfiles, "run_status": "output_files_transferring", "sbg_export_ids": export_id_list, "sbg_mounted_volume_ids": wr.sbg_mounted_volume_ids})



## function that returns a requests response in a nicely indented json format.
def format_response (response):
    return json.dumps(json.loads(response.text), indent=4)


def post_to_metadata(key, post_item, schema_name):
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

