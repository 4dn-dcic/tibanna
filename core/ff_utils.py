import datetime
import json
import time
from uuid import uuid4
import random
import os
from wranglertools import fdnDCIC

SECRET = os.environ.get("SECRET", '')
HIGLASS_SERVER = os.environ.get("HIGLASS_SERVER", "localhost")
HIGLASS_USER = os.environ.get("HIGLASS_USER")
HIGLASS_PASS = os.environ.get("HIGLASS_PASS")
HIGLASS_BUCKETS = ['elasticbeanstalk-fourfront-webprod-wfoutput',
                   'elasticbeanstalk-fourfront-webdev-wfoutput']


class FdnConnectionException(Exception):
    pass


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
                        run_status='started', run_platform='AWSEM', run_url='', tag=None,
                        aliases=None, awsem_postrun_json=None, submitted_by=None, extra_meta=None,
                        **kwargs):

    input_files = [] if input_files is None else input_files
    parameters = [] if parameters is None else parameters
    if award is None:
        award = '1U01CA200059-01'
    if lab is None:
        lab = '4dn-dcic-lab'

    if title is None:
        if tag is None:
            title = app_name + " run " + str(datetime.datetime.now())
        else:
            title = app_name + ' ' + tag + " run " + str(datetime.datetime.now())

    return WorkflowRunMetadata(workflow=workflow, app_name=app_name, input_files=input_files,
                               parameters=parameters, uuid=uuid, award=award,
                               lab=lab, run_platform=run_platform, run_url=run_url,
                               title=title, output_files=output_files, run_status=run_status,
                               aliases=aliases, awsem_postrun_json=awsem_postrun_json,
                               submitted_by=submitted_by, extra_meta=extra_meta)


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
                 run_url='', aliases=None, awsem_postrun_json=None,
                 submitted_by=None, extra_meta=None, **kwargs):
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
        if aliases:
            if isinstance(aliases, basestring):
                aliases = [aliases, ]
            self.aliases = aliases
        self.input_files = input_files
        if output_files:
            self.output_files = output_files
        self.parameters = parameters
        self.award = award
        self.lab = lab
        if awsem_postrun_json:
            self.awsem_postrun_json = awsem_postrun_json
        if submitted_by:
            self.submitted_by = submitted_by

        if extra_meta:
            for k, v in extra_meta.iteritems():
                self.__dict__[k] = v

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
                 award='1U01CA200059-01', status='to be uploaded by workflow',
                 md5sum=None, file_size=None,
                 other_fields=None,
                 **kwargs):
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
        if md5sum:
            self.md5sum = md5sum
        if file_size:
            self.file_size = file_size
        if other_fields:
            for field in other_fields:
                setattr(self, field, other_fields[field])

    def as_dict(self):
        return self.__dict__

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def post(self, key):
        return post_to_metadata(self.as_dict(), "file_processed", key=key)

    @classmethod
    def get(cls, uuid, key, return_data=False):
        data = get_metadata(uuid, key=key)
        if type(data) is not dict:
            raise Exception("unable to find object with unique key of %s" % uuid)
        if 'FileProcessed' not in data.get('@type', {}):
            raise Exception("you can only load ProcessedFiles into this object")

        pf = ProcessedFileMetadata(**data)
        if return_data:
            return pf, data
        else:
            return pf


def fdn_connection(key='', connection=None):
    assert key or connection

    if not connection:
        try:
            fdn_key = fdnDCIC.FDN_Key(key, 'default')
            connection = fdnDCIC.FDN_Connection(fdn_key)
        except Exception as e:
            raise Exception("Unable to connect to server with check keys : %s" % e)
    return connection


def patch_metadata(patch_item, obj_id='', key='', connection=None, url_addon=None):
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
    # default to always get from database
    try:
        connection = fdn_connection(key, connection)
    except Exception as e:
        raise FdnConnectionException("%s" % e)
    sleep = [2, 4, 6]
    for wait in sleep:
        try:
            res = fdnDCIC.get_FDN(obj_id, connection, frame=frame)
        except:
            time.sleep(wait)
            continue
        if 'error' in res.get('@type', []):
            time.sleep(wait)
            continue
        else:
            return res
    # if loop did not solve the problem
    # TODO: throw error here
    print('get_metdata is not working for', obj_id)
    return


def post_to_metadata(post_item, schema_name, key='', connection=None):
    connection = fdn_connection(key, connection)
    if schema_name == 'file_processed':
        url_addon = '?force_md5'
    else:
        url_addon = None
    try:
        response = fdnDCIC.new_FDN(connection, schema_name, post_item, url_addon=url_addon)
        if (response.get('status') == 'error' and response.get('detail') == 'UUID conflict'):
            # item already posted lets patch instead
            response = patch_metadata(post_item, connection=connection, url_addon=url_addon)
        elif response.get('status') == 'error':
            raise Exception("error %s \n unable to post data to schema %s, data: %s" %
                            (response, schema_name, post_item))
    except Exception as e:
        raise Exception("error %s \nunable to post data to schema %s, data: %s" %
                        (e, schema_name, post_item))
    return response


def delete_field(post_json, del_field, connection=None):
    """Does a put to delete the given field."""
    # make sure we get from database
    url_addon = '&datastore=database'
    my_uuid = post_json.get("uuid")
    my_accession = post_json.get("accesion")
    raw_json = fdnDCIC.get_FDN(my_uuid, connection, frame="raw", url_addon=url_addon)
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


def aslist(x):
    if isinstance(x, list):
        return x
    else:
        return [x]


def get_extra_file_key(infile_format, infile_key, extra_file_format, fe_map):
    infile_extension = fe_map.get(infile_format)
    extra_file_extension = fe_map.get(extra_file_format)
    return infile_key.replace(infile_extension, extra_file_extension)


def merge_source_experiments(input_file_uuids, ff_keys):
    """Connects to fourfront and get source experiment info as a unique list
    Takes a list of input file uuids
    """
    pf_source_experiments = set()
    for input_file_uuid in input_file_uuids:
        pf_source_experiments.update(get_source_experiment(input_file_uuid, ff_keys))
    return list(pf_source_experiments)


def get_source_experiment(input_file_uuid, ff_keys):
    """Connects to fourfront and get source experiment info as a unique list
    Takes a single input file uuid
    """
    pf_source_experiments_set = set()
    inf_uuids = aslist(input_file_uuid)
    for inf_uuid in inf_uuids:
        infile_meta = get_metadata(inf_uuid, key=ff_keys)
        if infile_meta.get('experiments'):
            for exp in infile_meta.get('experiments'):
                exp_uuid = get_metadata(exp, key=ff_keys).get('uuid')
                pf_source_experiments_set.add(exp_uuid)
        if infile_meta.get('source_experiments'):
            pf_source_experiments_set.update(infile_meta.get('source_experiments'))
    return list(pf_source_experiments_set)


def get_format_extension_map(ff_keys):
    """get format-extension map"""
    try:
        fp_schema = get_metadata("profiles/file_processed.json", key=ff_keys)
        fe_map = fp_schema.get('file_format_file_extension')
    except Exception as e:
        raise Exception("Can't get format-extension map from file_processed schema. %s\n" % e)
    return fe_map
