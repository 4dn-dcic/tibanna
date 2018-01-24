import datetime
import json
import time
from uuid import uuid4
import random

from wranglertools import fdnDCIC


def convert_param(parameter_dict, vals_as_string=False):
    '''
    converts dictionary format {argument_name: value, argument_name: value, ...}
    to {'workflow_argument_name': argument_name, 'value': value}
    '''
    print(str(parameter_dict))
    metadata_parameters = []
    for k, v in parameter_dict.iteritems():
        # we need this to be a float or integer if it really is, else a string
        if not vals_as_string:
            try:
                v = float(v)
                if v % 1 == 0:
                    v = int(v)
            except ValueError:
                v = str(v)
        else:
            v = str(v)

        metadata_parameters.append({"workflow_argument_name": k, "value": v})

    print(str(metadata_parameters))
    return metadata_parameters


def create_ffmeta_awsem(workflow, app_name, input_files=None, parameters=None, title=None, uuid=None,
                        output_files=None, award='1U01CA200059-01', lab='4dn-dcic-lab',
                        run_status='started', run_platform='AWSEM', run_url='', tag=None, **kwargs):

    input_files = [] if input_files is None else input_files
    parameters = [] if parameters is None else parameters

    if title is None:
        if tag is None:
            title = app_name + " run " + str(datetime.datetime.now())
        else:
            title = app_name + ' ' + tag + " run " + str(datetime.datetime.now())

    return WorkflowRunMetadata(workflow=workflow, app_name=app_name, input_files=input_files,
                               parameters=parameters, uuid=uuid, award=award,
                               lab=lab, run_platform=run_platform, run_url=run_url,
                               title=title, output_files=output_files, run_status=run_status)


def create_ffmeta(sbg, workflow, input_files=None, parameters=None, title=None, sbg_task_id=None,
                  sbg_mounted_volume_ids=None, sbg_import_ids=None, sbg_export_ids=None, uuid=None,
                  award='1U01CA200059-01', lab='4dn-dcic-lab', run_platform='SBG',
                  output_files=None, run_status='started', **kwargs):

    input_files = [] if input_files is None else input_files
    parameters = [] if parameters is None else parameters
    # TODO: this probably is not right
    sbg_export_ids = [] if sbg_export_ids is None else sbg_export_ids

    if title is None:
        title = sbg.app_name + " run " + str(datetime.datetime.now())

    if sbg_task_id is None:
        sbg_task_id = sbg.task_id

    if not sbg_mounted_volume_ids:
        try:
            sbg.volume_list[0]['name']
            sbg_mounted_volume_ids = [x['name'] for x in sbg.volume_list]
        except:
            sbg_mounted_volume_ids = [x for x in sbg.volume_list]

    if not sbg_import_ids:
        sbg_import_ids = sbg.import_id_list

    if not output_files:
        output_files = sbg.export_report
    else:
        # self.output_files may contain e.g. file_format and file_type information.
        for of in output_files:
            for of2 in sbg.export_report:
                if of['workflow_argument_name'] == of2['workflow_argument_name']:
                    for k, v in of2.iteritems():
                        of[k] = v

    return WorkflowRunMetadata(workflow, sbg.app_name, input_files, parameters,
                               sbg_task_id, sbg_import_ids, sbg_export_ids,
                               sbg_mounted_volume_ids, uuid,
                               award, lab, run_platform, title, output_files, run_status, **kwargs)


class WorkflowRunMetadata(object):
    '''
    fourfront metadata
    '''

    def __init__(self, workflow, app_name, input_files=[],
                 parameters=[], sbg_task_id=None,
                 sbg_import_ids=None, sbg_export_ids=None,
                 sbg_mounted_volume_ids=None, uuid=None,
                 award='1U01CA200059-01', lab='4dn-dcic-lab',
                 run_platform='SBG', title=None, output_files=None,
                 run_status='started', awsem_job_id=None,
                 run_url='', **kwargs):
        """Class for WorkflowRun that matches the 4DN Metadata schema
        Workflow (uuid of the workflow to run) has to be given.
        Workflow_run uuid is auto-generated when the object is created.
        """
        if run_platform == 'SBG':
            self.sbg_app_name = app_name
            # self.app_name = app_name
            if sbg_task_id is None:
                self.sbg_task_id = ''
            else:
                self.sbg_task_id = sbg_task_id
            if sbg_mounted_volume_ids is None:
                self.sbg_mounted_volume_ids = []
            else:
                self.sbg_mounted_volume_ids = sbg_mounted_volume_ids
            if sbg_import_ids is None:
                self.sbg_import_ids = []
            else:
                self.sbg_import_ids = sbg_import_ids
            if sbg_export_ids is None:
                self.sbg_export_ids = []
            else:
                self.sbg_export_ids = sbg_export_ids
        elif run_platform == 'AWSEM':
            self.awsem_app_name = app_name
            # self.app_name = app_name
            if awsem_job_id is None:
                self.awsem_job_id = ''
            else:
                self.awsem_job_id = awsem_job_id
        else:
            raise Exception("invalid run_platform {} - it must be either SBG or AWSEM".format(run_platform))

        self.run_status = run_status
        self.uuid = uuid if uuid else str(uuid4())
        self.workflow = workflow
        self.run_platform = run_platform
        if run_url:
            self.run_url = run_url

        self.title = title
        self.input_files = input_files
        if output_files:
            self.output_files = output_files
        self.parameters = parameters
        self.award = award
        self.lab = lab

    def append_outputfile(self, outjson):
        self.output_files.append(outjson)

    def append_volumes(self, sbg_volume):
        self.sbg_mounted_volume_ids.append(sbg_volume.id)

    def as_dict(self):
        return self.__dict__

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def post(self, key, type_name=None):
        if not type_name:
            if self.run_platform == 'SBG':
                type_name = 'workflow_run_sbg'
            elif self.run_platform == 'AWSEM':
                type_name = 'workflow_run_awsem'
            else:
                raise Exception("cannot determine workflow schema type: SBG or AWSEM?")
        return post_to_metadata(self.as_dict(), type_name, key=key)


class ProcessedFileMetadata(object):
    def __init__(self, uuid=None, accession=None, file_format='', lab='4dn-dcic-lab',
                 extra_files=None, source_experiments=None,
                 award='1U01CA200059-01', status='to be uploaded by workflow', **kwargs):
        self.uuid = uuid if uuid else str(uuid4())
        self.accession = accession if accession else generate_rand_accession()
        self.status = status
        self.lab = lab
        self.award = award
        self.file_format = file_format
        if extra_files:
            self.extra_files = extra_files
        if source_experiments:
            self.source_experiments = source_experiments

    def as_dict(self):
        return self.__dict__

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def post(self, key):
        return post_to_metadata(self.as_dict(), "file_processed", key=key)

    @classmethod
    def get(cls, uuid, key):
        data = get_metadata(uuid, key=key)
        if type(data) is not dict:
            raise Exception("unable to find object with unique key of %s" % uuid)
        if 'FileProcessed' not in data.get('@type'):
            raise Exception("you can only load ProcessedFiles into this object")

        return ProcessedFileMetadata(**data)


def fdn_connection(key='', connection=None):
    assert key or connection

    if not connection:
        try:
            fdn_key = fdnDCIC.FDN_Key(key, 'default')
            connection = fdnDCIC.FDN_Connection(fdn_key)
        except Exception as e:
            raise Exception("Unable to connect to server with check keys : %s" % e)
    return connection


def patch_metadata(patch_item, obj_id='', key='', connection=None):
    '''
    obj_id can be uuid or @id for most object
    '''

    connection = fdn_connection(key, connection)

    obj_id = obj_id if obj_id else patch_item['uuid']

    try:
        response = fdnDCIC.patch_FDN(obj_id, connection, patch_item)

        if response.get('status') == 'error':
            raise Exception("error %s \n unable to patch obj: %s \n with  data: %s" %
                            (response, obj_id, patch_item))
    except Exception as e:
        raise Exception("error %s \nunable to patch object %s \ndata: %s" % (e, obj_id, patch_item))
    return response


def get_metadata(obj_id, key='', connection=None, frame="object"):
    connection = fdn_connection(key, connection)
    res = fdnDCIC.get_FDN(obj_id, connection, frame=frame)
    retry = 1
    sleep = [2, 4, 12]
    while 'error' in res.get('@type', []) and retry < 3:
        time.sleep(sleep[retry])
        retry += 1
        res = fdnDCIC.get_FDN(obj_id, connection, frame=frame)

    return res


def post_to_metadata(post_item, schema_name, key='', connection=None):
    connection = fdn_connection(key, connection)

    try:
        response = fdnDCIC.new_FDN(connection, schema_name, post_item)
        if (response.get('status') == 'error' and response.get('detail') == 'UUID conflict'):
            # item already posted lets patch instead
            response = patch_metadata(post_item, connection=connection)
        elif response.get('status') == 'error':
            raise Exception("error %s \n unable to post data to schema %s, data: %s" %
                            (response, schema_name, post_item))
    except Exception as e:
        raise Exception("error %s \nunable to post data to schema %s, data: %s" %
                        (e, schema_name, post_item))
    return response


def delete_field(post_json, del_field, connection=None):
    """Does a put to delete the given field."""
    my_uuid = post_json.get("uuid")
    my_accession = post_json.get("accesion")
    raw_json = fdnDCIC.get_FDN(my_uuid, connection, frame="raw")
    # check if the uuid is in the raw_json
    if not raw_json.get("uuid"):
        raw_json["uuid"] = my_uuid
    # if there is an accession, add it to raw so it does not created again
    if my_accession:
        if not raw_json.get("accession"):
            raw_json["accession"] = my_accession
    # remove field from the raw_json
    if raw_json.get(del_field):
        del raw_json[del_field]
    # Do the put with raw_json
    try:
        response = fdnDCIC.put_FDN(my_uuid, connection, raw_json)
        if response.get('status') == 'error':
            raise Exception("error %s \n unable to delete field: %s \n of  item: %s" %
                            (response, del_field, my_uuid))
    except Exception as e:
        raise Exception("error %s \n unable to delete field: %s \n of  item: %s" %
                        (e, del_field, my_uuid))
    return response


def generate_rand_accession():
    rand_accession = ''
    for i in xrange(7):
        r = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789')
        rand_accession += r
    accession = "4DNFI"+rand_accession
    return accession
