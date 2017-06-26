# -*- coding: utf-8 -*-
import logging
import json
import boto3
from core import sbg_utils, ff_utils
from core.utils import Tibanna, ensure_list

LOG = logging.getLogger(__name__)
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
    app_name = event.get('app_name')
    parameter_dict = event.get('parameters')
    workflow_uuid = event.get('workflow_uuid')
    output_bucket = event.get('output_bucket')
    tibanna_settings = event.get('_tibanna', {})
    # if they don't pass in env guess it from output_bucket
    env = tibanna_settings.get('env', '-'.join(output_bucket.split('-')[1:-1]))
    # tibanna provides access to keys based on env and stuff like that
    tibanna = Tibanna(env, s3_keys=event.get('s3_keys'), ff_keys=event.get('ff_keys'),
                      settings=tibanna_settings)

    LOG.info("input data is %s" % event)
    # represents the SBG info we need
    sbg = sbg_utils.create_sbg_workflow(app_name, tibanna.sbg_keys)
    LOG.info("sbg is %s" % sbg.__dict__)

    # represents the workflow metadata to be stored in fourfront
    parameters, _ = sbg_utils.to_sbg_workflow_args(parameter_dict, vals_as_string=True)

    # get argument format & type info from workflow
    workflow_info = ff_utils.get_metadata(workflow_uuid, key=tibanna.ff_keys)
    LOG.info("workflow info  %s" % workflow_info)
    if 'error' in workflow_info.get('@type', []):
        raise Exception("FATAL, can't lookupt workflow info for % fourfront" % workflow_uuid)

    # This dictionary has a key 'arguments' with a value
    # { 'workflow_argument_name': ..., 'argument_type': ..., 'argument_format': ... }

    # get format-extension map
    try:
        fp_schema = ff_utils.get_metadata("profiles/file_processed.json", key=tibanna.ff_keys)
        fe_map = fp_schema.get('file_format_file_extension')
    except Exception as e:
        LOG.error("Can't get format-extension map from file_processed schema. %s\n" % e)

    # processed file metadata
    output_files = []
    try:
        if 'arguments' in workflow_info:
            pf_meta = []
            for arg in workflow_info.get('arguments'):
                if (arg.get('argument_type') in
                   ['Output processed file', 'Output report file', 'Output QC file']):

                    of = dict()
                    of['workflow_argument_name'] = arg.get('workflow_argument_name')
                    of['type'] = arg.get('argument_type')
                    if 'argument_format' in arg:
                        # These are not processed files but report or QC files.
                        pf = ff_utils.ProcessedFileMetadata(file_format=arg.get('argument_format'))
                        try:
                            resp = pf.post(key=tibanna.ff_keys)  # actually post processed file metadata here
                            resp = resp.get('@graph')[0]
                            of['upload_key'] = resp.get('upload_key')
                            of['value'] = resp.get('uuid')
                        except Exception as e:
                            LOG.error("Failed to post Processed file metadata. %s\n" % e)
                            LOG.error("resp" + str(resp) + "\n")
                            raise e
                        of['format'] = arg.get('argument_format')
                        of['extension'] = fe_map.get(arg.get('argument_format'))
                        pf_meta.append(pf)
                    output_files.append(of)

    except Exception as e:
        LOG.error("output_files = " + str(output_files) + "\n")
        LOG.error("Can't prepare output_files information. %s\n" % e)
        raise e

    # create the ff_meta output info
    input_files = []
    for input_file in input_file_list:
        for idx, uuid in enumerate(ensure_list(input_file['uuid'])):
            input_files.append({'workflow_argument_name': input_file['workflow_argument_name'],
                                'value': uuid, 'ordinal': idx + 1})
    LOG.info("input_files is %s" % input_files)

    ff_meta = ff_utils.create_ffmeta(sbg, workflow_uuid, input_files, parameters,
                                     run_url=tibanna.settings.get('url', ''), output_files=output_files)
    LOG.info("ff_meta is %s" % ff_meta.__dict__)

    # store metadata so we know the run has started
    ff_meta.post(key=tibanna.ff_keys)

    # mount all input files to sbg this will also update sbg to store the import_ids
    for infile in input_file_list:
        imps = mount_on_sbg(infile, tibanna.s3_keys, sbg)
        infile['import_ids'] = imps

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
            'pf_meta': [meta.as_dict() for meta in pf_meta],
            "_tibanna": tibanna.as_dict(),
            "parameter_dict": parameter_dict}


#################
# Extra Functions
#################


def mount_on_sbg(input_file, s3_keys, sbg):
    # get important info from input_file json
    bucket = input_file.get('bucket_name')
    keys = ensure_list(input_file.get('object_key'))
    key_uuids = ensure_list(input_file.get('uuid'))

    import_ids = []
    for key, key_uuid in zip(keys, key_uuids):
        imp_id = mount_one_on_sbg(key, key_uuid, bucket, s3_keys, sbg)
        import_ids.append(imp_id)
    return imp_id


def mount_one_on_sbg(key, key_uuid, bucket, s3_keys, sbg):
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
        self.lab = "4dn-dcic-lab"
        self.submitted_by = "4dndcic@gmail.com"
        self.award = "1U01CA200059-01"

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)


# This function returns a new workflow_run dictionary; it should be updated
# so that existing workflow_run objects are modified.
# Input files are omitted here. They should already be in the workflow_run.
def get_output_patch_for_workflow_run(sbg_run_detail_resp, processed_files_report, sbg_volume, wr):

    outputfiles = []
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

