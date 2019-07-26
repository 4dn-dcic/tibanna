import json
import os
import datetime
import boto3
import gzip
from uuid import uuid4
from dcicutils.ff_utils import (
    get_metadata,
    post_metadata,
    patch_metadata,
    generate_rand_accession,
    search_metadata
)
from dcicutils.s3_utils import s3Utils
from tibanna.nnested_array import (
    flatten,
    create_dim
)
from tibanna.utils import (
    printlog
)
from tibanna.base import (
    SerializableObject
)
from tibanna.awsem import (
    AwsemPostRunJson
)
from .config import (
    higlass_config
)
from .exceptions import (
    TibannaStartException,
)

def create_ffmeta_awsem(workflow, app_name, app_version=None, input_files=None,
                        parameters=None, title=None, uuid=None,
                        output_files=None, award='1U01CA200059-01', lab='4dn-dcic-lab',
                        run_status='started', run_platform='AWSEM', run_url='', tag=None,
                        aliases=None, awsem_postrun_json=None, submitted_by=None, extra_meta=None,
                        jobid=None,
                        **kwargs):

    input_files = [] if input_files is None else input_files
    parameters = [] if parameters is None else parameters
    if award is None:
        award = '1U01CA200059-01'
    if lab is None:
        lab = '4dn-dcic-lab'

    if title is None:
        if app_version:
            title = app_name + ' ' + app_version
        else:
            title = app_name
        if tag:
            title = title + ' ' + tag
        title = title + " run " + str(datetime.datetime.now())

    return WorkflowRunMetadata(workflow=workflow, awsem_app_name=app_name, input_files=input_files,
                               parameters=parameters, uuid=uuid, award=award,
                               lab=lab, run_platform=run_platform, run_url=run_url,
                               title=title, output_files=output_files, run_status=run_status,
                               aliases=aliases, awsem_postrun_json=awsem_postrun_json,
                               submitted_by=submitted_by, extra_meta=extra_meta, awsem_job_id=jobid)


class WorkflowRunMetadata(object):
    '''
    fourfront metadata
    '''

    def __init__(self, workflow, awsem_app_name, input_files=[],
                 parameters=[], uuid=None,
                 award='1U01CA200059-01', lab='4dn-dcic-lab',
                 run_platform='AWSEM', title=None, output_files=None,
                 run_status='started', awsem_job_id=None,
                 run_url='', aliases=None, awsem_postrun_json=None,
                 submitted_by=None, extra_meta=None, **kwargs):
        """Class for WorkflowRun that matches the 4DN Metadata schema
        Workflow (uuid of the workflow to run) has to be given.
        Workflow_run uuid is auto-generated when the object is created.
        """
        if run_platform == 'AWSEM':
            self.awsem_app_name = awsem_app_name
            # self.app_name = app_name
            if awsem_job_id is None:
                self.awsem_job_id = ''
            else:
                self.awsem_job_id = awsem_job_id
        else:
            raise Exception("invalid run_platform {} - it must be AWSEM".format(run_platform))

        self.run_status = run_status
        self.uuid = uuid if uuid else str(uuid4())
        self.workflow = workflow
        self.run_platform = run_platform
        if run_url:
            self.run_url = run_url

        self.title = title
        if aliases:
            if isinstance(aliases, basestring):  # noqa
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
            for k, v in iter(extra_meta.items()):
                self.__dict__[k] = v

    def append_outputfile(self, outjson):
        self.output_files.append(outjson)

    def as_dict(self):
        return self.__dict__

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def post(self, key, type_name=None):
        if not type_name:
            if self.run_platform == 'AWSEM':
                type_name = 'workflow_run_awsem'
            else:
                raise Exception("cannot determine workflow schema type from the run platform: should be AWSEM.")
        return post_metadata(self.as_dict(), type_name, key=key)

    def patch(self, key, type_name=None):
        return patch_metadata(self.as_dict(), key=key)


class ProcessedFileMetadata(object):
    def __init__(self, uuid=None, accession=None, file_format='', lab='4dn-dcic-lab',
                 extra_files=None, source_experiments=None,
                 award='1U01CA200059-01', status='to be uploaded by workflow',
                 md5sum=None, file_size=None, other_fields=None, **kwargs):
        self.uuid = uuid if uuid else str(uuid4())
        self.accession = accession if accession else generate_rand_accession()
        self.status = status
        self.lab = lab
        self.award = award
        self.file_format = parse_formatstr(file_format)
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
        return post_metadata(self.as_dict(), "file_processed", key=key, add_on='force_md5')

    def patch(self, key, fields=None):
        if fields:
            patch_json = {k: v for k, v in self.as_dict().items() if k in fields}
        else:
            patch_json = self.as_dict()
        print(patch_json)
        return patch_metadata(patch_json, key=key, add_on='force_md5')

    @classmethod
    def get(cls, uuid, key, ff_env=None, check_queue=False, return_data=False):
        data = get_metadata(uuid,
                            key=key,
                            ff_env=ff_env,
                            add_on='frame=object',
                            check_queue=check_queue)
        if type(data) is not dict:
            raise Exception("unable to find object with unique key of %s" % uuid)
        if 'FileProcessed' not in data.get('@type', {}):
            raise Exception("you can only load ProcessedFiles into this object")

        pf = ProcessedFileMetadata(**data)
        if return_data:
            return pf, data
        else:
            return pf

    def add_higlass_uid(self, higlass_uid):
        if higlass_uid:
            self.higlass_uid = higlass_uid


class WorkflowRunOutputFiles(object):
    def __init__(self, workflow_argument_name, argument_type, file_format=None, secondary_file_formats=None,
                 upload_key=None, uuid=None, extra_files=None):
        self.workflow_argument_name = workflow_argument_name
        self.type = argument_type
        if file_format:
            self.format = file_format
        if extra_files:
            self.extra_files = extra_files
        if secondary_file_formats:
            self.secondary_file_formats = secondary_file_formats
        if uuid:
            self.value = uuid
        if upload_key:
            self.upload_key = upload_key

    def as_dict(self):
        return self.__dict__


def parse_formatstr(file_format_str):
    if not file_format_str:
        return None
    return file_format_str.replace('/file-formats/', '').replace('/', '')


def create_ordinal(a):
    if isinstance(a, list):
        return list(range(1, len(a)+1))
    else:
        return 1


def create_ffmeta_input_files_from_pony_input_file_list(input_file_list):
    input_files_for_ffmeta = []
    for input_file in input_file_list:
        dim = flatten(create_dim(input_file['uuid']))
        if not dim:  # singlet
            dim = '0'
        uuid = flatten(input_file['uuid'])
        ordinal = create_ordinal(uuid)
        for d, u, o in zip(aslist(dim), aslist(uuid), aslist(ordinal)):
            infileobj = InputFileForWFRMeta(input_file['workflow_argument_name'], u, o,
                                            input_file.get('format_if_extra', ''), d)
            input_files_for_ffmeta.append(infileobj.as_dict())
    printlog("input_files_for_ffmeta is %s" % input_files_for_ffmeta)
    return input_files_for_ffmeta


class InputFileForWFRMeta(object):
    def __init__(self, workflow_argument_name=None, value=None, ordinal=None, format_if_extra=None, dimension=None):
        self.workflow_argument_name = workflow_argument_name
        self.value = value
        self.ordinal = ordinal
        if dimension:
            self.dimension = dimension
        if format_if_extra:
            self.format_if_extra = format_if_extra

    def as_dict(self):
        return self.__dict__


def aslist(x):
    if isinstance(x, list):
        return x
    else:
        return [x]


def ensure_list(val):
    if isinstance(val, (list, tuple)):
        return val
    return [val]


def get_extra_file_key(infile_format, infile_key, extra_file_format, fe_map):
    infile_extension = fe_map.get_extension(infile_format)
    extra_file_extension = fe_map.get_extension(extra_file_format)
    if not infile_extension or not extra_file_extension:
        errmsg = "Extension not found for infile_format %s (key=%s)" % (infile_format, infile_key)
        errmsg += "extra_file_format %s" % extra_file_format
        errmsg += "(infile extension %s, extra_file_extension %s)" % (infile_extension, extra_file_extension)
        raise Exception(errmsg)
    return infile_key.replace(infile_extension, extra_file_extension)


class FormatExtensionMap(object):
    def __init__(self, ff_keys):
        try:
            printlog("Searching in server : " + ff_keys['server'])
            ffe_all = search_metadata("/search/?type=FileFormat&frame=object", key=ff_keys)
        except Exception as e:
            raise Exception("Can't get the list of FileFormat objects. %s\n" % e)
        self.fe_dict = dict()
        printlog("**ffe_all = " + str(ffe_all))
        for k in ffe_all:
            file_format = k['file_format']
            self.fe_dict[file_format] = \
                {'standard_extension': k['standard_file_extension'],
                 'other_allowed_extensions': k.get('other_allowed_extensions', []),
                 'extrafile_formats': k.get('extrafile_formats', [])
                 }

    def get_extension(self, file_format):
        if file_format in self.fe_dict:
            return self.fe_dict[file_format]['standard_extension']
        else:
            return None

    def get_other_extensions(self, file_format):
        if file_format in self.fe_dict:
            return self.fe_dict[file_format]['other_allowed_extensions']
        else:
            return []


def get_source_experiment(input_file_uuid, ff_keys, ff_env):
    """
    Connects to fourfront and get source experiment info as a unique list
    Takes a single input file uuid.
    """
    pf_source_experiments_set = set()
    inf_uuids = aslist(flatten(input_file_uuid))
    for inf_uuid in inf_uuids:
        infile_meta = get_metadata(inf_uuid,
                                   key=ff_keys,
                                   ff_env=ff_env,
                                   add_on='frame=object')
        if infile_meta.get('experiments'):
            for exp in infile_meta.get('experiments'):
                exp_obj = get_metadata(exp,
                                       key=ff_keys,
                                       ff_env=ff_env,
                                       add_on='frame=raw')
                pf_source_experiments_set.add(exp_obj['uuid'])
        if infile_meta.get('source_experiments'):
            # this field is an array of strings, not linkTo's
            pf_source_experiments_set.update(infile_meta.get('source_experiments'))
    return list(pf_source_experiments_set)


def merge_source_experiments(input_file_uuids, ff_keys, ff_env=None):
    """
    Connects to fourfront and get source experiment info as a unique list
    Takes a list of input file uuids.
    """
    pf_source_experiments = set()
    for input_file_uuid in input_file_uuids:
        pf_source_experiments.update(get_source_experiment(input_file_uuid, ff_keys, ff_env))
    return list(pf_source_experiments)


class TibannaSettings(object):

    def __init__(self, env, ff_keys=None, sbg_keys=None, settings=None):
        self.env = env
        self.s3 = s3Utils(env=env)

        if not ff_keys:
            ff_keys = self.s3.get_access_keys()
        self.ff_keys = ff_keys

        if not settings:
            settings = {}
        self.settings = settings

    def get_reporter(self):
        '''
        a reporter is a generic name for somethign that reports on the results of each step
        of the workflow.  For our immediate purposes this will return ffmetadata object
        (which is a connection to our metadata repository, eventually it should, through
        polymorphism support any type of reporter a user might develop.
        '''
        return None

    def get_runner(self):
        '''
        a runner is an object that implements a set api to run the workflow one step at a time.
        Currently this is sbg for us.
        '''
        return None

    def as_dict(self):
        return {'env': self.env,
                'settings': self.settings}


def current_env():
    return os.environ.get('ENV_NAME', 'test')


def is_prod():
    return current_env().lower() == 'prod'


class AwsemFile(object):
    '''Class for input, output, extra files that are embedded in the Awsem class.
    Its use for input files is mostly on getting input file accession
    to attach qc/report type output
    '''

    def __init__(self, bucket, key, runner, argument_type=None,
                 filesize=None, md5=None, format_if_extra=None, is_extra=False,
                 argument_name=None):
        self.bucket = bucket
        self.key = key
        self.s3 = s3Utils(self.bucket, self.bucket, self.bucket)
        self.runner = runner
        self.argument_type = argument_type
        self.filesize = filesize
        self.md5 = md5
        self.format_if_extra = format_if_extra
        self.argument_name = argument_name
        if self.format_if_extra or is_extra:
            self.is_extra = True
        else:
            self.is_extra = False

    @property
    def accession(self):
        '''if argument type is either 'Output processed file or 'Input file',
        returns accession. If not, returns None.'''
        if self.argument_type in ['Output processed file', 'Input file']:
            file_name = self.key.split('/')[-1]
            return file_name.split('.')[0].strip('/')
        else:
            return None

    @property
    def status(self):
        exists = self.s3.does_key_exist(self.key, self.bucket)
        if exists:
            return "COMPLETED"
        else:
            return "FAILED"

    def read(self):
        return self.s3.read_s3(self.key).strip()


class PonyFinal(SerializableObject):
    """This class integrates three different sources of information:
    postrunjson, workflowrun, processed_files,
    and does the final updates necessary"""
    def __init__(self, postrunjson, ff_meta, pf_meta=None, _tibanna=None, **kwargs):
        self.ff_meta = WorkflowRunMetadata(**ff_meta)
        self.postrunjson = AwsemPostRunJson(**postrunjson)
        if pf_meta:
            self.pf_output_files = {pf['uuid']: ProcessedFileMetadata(**pf) for pf in pf_meta}
        # if _tibanna is not set, still proceed with the other functionalities of the class
        self.tibanna_settings = None
        if _tibanna and 'env' in _tibanna:
            try:
                self.tibanna_settings = TibannaSettings(_tibanna['env'], settings=_tibanna)
            except Exception as e:
                raise TibannaStartException("%s" % e)
        self.pf_patch = dict()  # patch json for pfs

    @property
    def app_name(self):
        return self.postrunjson.Job.App.App_name

    # postrunjson-related basic functionalities
    @property
    def awsem_output_files(self):
        """this used to be called output_info"""
        return self.postrunjson.Job.Output.output_files

    @property
    def awsem_input_files(self):
        return self.postrunjson.Job.Input.Input_files_data

    # workflowrun-ralated basic functionalities
    @property
    def ff_output_files(self):
        """this used to be called output_files_meta"""
        return self.ff_meta.output_files

    @property
    def ff_input_files(self):
        return self.ff_meta.input_files

    @property
    def ff_files(self):
        return self.ff_input_files + self.ff_output_files

    def ff_output_file(self, argname=None, pf_uuid=None):
        if argname:
            pass
        elif pf_uuid:
            argname = self.pf2argname(pf_uuid)
        else:
            raise Exception("Either argname or pf_uuid must be provided")
        for v in self.ff_output_files:
            if argname == v['workflow_argument_name']:
                return v
        return None

    def ff_file(self, argname):
        for v in self.ff_files:
            if argname == v['workflow_argument_name']:
                return v
        return None

    @property
    def input_argnames(self):
        return list(self.awsem_input_files.keys())

    @property
    def output_argnames(self):
        return list(self.awsem_output_files.keys())

    def output_type(self, argname):
        for x in self.ff_output_files:
            if x['workflow_argument_name'] == argname:
                return x['type']
        return None

    # processed file-ralated basic functionalities
    def pf(self, pf_uuid):
        return self.pf_output_files.get(pf_uuid, None)
 
    def pf2argname(self, pf_uuid):
        for argname in self.output_argnames:
            if pf_uuid in self.pf_uuids(argname):
                return argname
        return None

    def pf_uuids(self, argname):
        uuids = []
        for of in self.ff_output_files:
            if argname == of['workflow_argument_name']:
                if of['type'] == 'Output processed file':
                    uuids.append(of['value'])
        return uuids

    def pf_extra_file(self, pf_uuid, file_format):
        for extra in self.pf(pf_uuid).extra_files:
            if cmp_fileformat(extra['file_format'], file_format):
                return extra
        return None

    # s3-related functionalities
    @property
    def outbucket(self):
        return self.postrunjson.Job.Output.output_bucket_directory

    def bucket(self, argname):
        if argname in self.awsem_output_files:
            return self.outbucket
        elif argname in self.awsem_input_files:
            return self.awsem_input_files[argname].dir_

    def s3(self, argname):
        return s3Utils(self.bucket(argname), self.bucket(argname), self.bucket(argname))

    def read(self, argname):
        """This function is useful for reading md5 report of qc report"""
        return self.s3(argname).read_s3(self.file_key(argname)).decode('utf-8', 'backslashreplace')

    # get file features
    def md5sum(self, argname=None, pf_uuid=None, secondary_key=None):
        if argname:
            pass
        elif pf_uuid:
            argname = self.pf2argname(pf_uuid)
        else:
            raise Exception("At least argname or pf_uuid must be provided to get md5sum")
        if secondary_key:
            for sf in self.awsem_output_files[argname].secondaryFiles:
                if sf.target == secondary_key:
                    return sf.md5sum
            return None
        return self.awsem_output_files[argname].md5sum

    def filesize(self, argname=None, pf_uuid=None, secondary_key=None):
        if argname:
            pass
        elif pf_uuid:
            argname = self.pf2argname(pf_uuid)
        else:
            raise Exception("At least argname or pf_uuid must be provided to get filesize")
        if secondary_key:
            for sf in self.awsem_output_files[argname].secondaryFiles:
                if sf.target == secondary_key:
                    return sf.size
            return None
        return self.awsem_output_files[argname].size

    def file_format(self, argname, secondary_key=None):
        for pf in self.ff_output_files:
            if pf['workflow_argument_name'] == argname:
                if secondary_key:
                    if 'extra_files' in pf:
                        for pfextra in pf['extra_files']:
                            if pfextra['upload_key'] == secondary_key:
                                return parse_formatstr(pfextra['file_format'])
                        printlog("No extra file matching key %s" % secondary_key)
                        return None
                    printlog("No extra file for argname %s" % argname)
                    return None
                else:
                    return pf['format']
        printlog("No workflow run output file matching argname %s" % argname)
        return None

    def file_key(self, argname=None, pf_uuid=None, secondary_format=None):
        """returns file object_key on the bucket, either through argname or
        processed file uuid (pf_uuid). To get the file key of a secondary file,
        use secondary_format - this option is valid only with pf_uuid.
        Getting a file key through argname is mainly for getting non-processed files
        like md5 or qc reports"""
        if argname:
            if argname in self.awsem_output_files:
                return self.awsem_output_files[argname].target
            elif argname in self.awsem_input_files:
                return self.awsem_input_files[argname].path
        elif pf_uuid:
            of = self.ff_output_file(pf_uuid=pf_uuid)
            if of:
                if secondary_format:
                    for extra in of['extra_files']:
                        if cmp_fileformat(extra['file_format'], secondary_format):
                            return extra['upload_key']
                    raise Exception("no extra file with format %s" % secondary_format)
                else:
                    return of['upload_key']
        else:
            raise Exception("Either argname or pf must be provided to get a file_key")

    def accessions(self, argname):
        accessions = []
        for v in self.ff_files:
            if argname == v['workflow_argument_name']:
                if v['type'] in ['Output processed file', 'Input file']:
                    file_name = v['upload_key'].split('/')[-1]
                    accession = file_name.split('.')[0].strip('/')
                    accessions.append(accession)
        return accessions

    def format_if_extras(self, argname):
        format_if_extras = []
        for v in self.ff_files:
            if argname == v['workflow_argument_name'] and 'format_if_extra' in v:
                format_if_extras.append(v['format_if_extra'])
        return format_if_extras
       
    def status(self, argname=None, pf_uuid=None):
        """check file existence as status either per argname or per pf object"""
        if argname:
            key = self.file_key(argname)
        elif pf_uuid:
            key = self.file_key(pf_uuid=pf_uuid)
            argname = self.pf2argname(pf_uuid)
        else:
            raise Exception("Either argname or pf_uuid must be provided to get status.")
        if not isinstance(key, list):
            key = [key]
        for k in key:
            try:
                exists = self.s3(argname).does_key_exist(key, self.bucket(argname))
                if not exists:
                    return "FAILED"
            except:
                return "FAILED" 
        return "COMPLETED"

    def genome_assembly(self, pf_uuid):
        if hasattr('genome_assembly', self.pf(pf_uuid)):
            return self.pf(pf_uuid).genome_assembly
        else:
            return None

    # update functions for PF
    def update_all_pfs(self):
        for pf_uuid in self.pf_output_files:
            self.update_pf(pf_uuid)

    def update_pf(self, pf_uuid):
        if self.status(pf_uuid=pf_uuid) == 'COMPLETED':
            self.add_updates_to_pf(pf_uuid)
            self.add_updates_to_pf_extra(pf_uuid)
            self.add_higlass_to_pf(pf_uuid)

    def add_to_pf_patch(self, pf_uuid, fields):
        """add entries from pf object to pf_patch for a later pf patch"""
        if not isinstance(fields, list):
            if pf_uuid not in self.pf_patch:
                self.pf_patch = {pf_uuid: {}}
            field_val = self.pf(pf_uuid).__getattribute__(fields)
            self.pf_patch[pf_uuid].update({fields: field_val})
        else:
            for f in fields:
                self.add_to_pf_patch(pf_uuid, f)

    def add_updates_to_pf(self, pf_uuid):
        """update md5sum, file_size, status for pf itself"""
        # update the class object
        self.pf(pf_uuid).md5sum = self.md5sum(pf_uuid=pf_uuid)
        self.pf(pf_uuid).file_size = self.filesize(pf_uuid=pf_uuid)
        self.pf(pf_uuid).status = 'uploaded'
        # prepare for fourfront patch
        self.add_to_pf_patch(pf_uuid, ['md5sum', 'file_size', 'status'])

    def add_updates_to_pf_extra(self, pf_uuid):
        """update md5sum, file_size, status for extra file"""
        argname = self.pf2argname(pf_uuid)
        ffout = self.ff_output_file(argname)
        if 'extra_files' in ffout:
            for extra in ffout['extra_files']:
                md5 = self.md5sum(pf_uuid=pf_uuid, secondary_key=extra['upload_key'])
                size = self.filesize(pf_uuid=pf_uuid, secondary_key=extra['upload_key'])
                pf_extra = self.pf_extra_file(pf_uuid, extra['file_format'])
                # update the class object
                pf_extra['md5sum'] = md5
                pf_extra['file_size'] = size
                pf_extra['status'] = 'uploaded'
            # prepare for fourfront patch
            self.add_to_pf_patch(pf_uuid, 'extra_files')

    def add_higlass_to_pf(self, pf_uuid):
        if self.bucket(pf_uuid) not in ff_utils.HIGLASS_BUCKETS:
            return None
        higlass_uid = None
        for hgcf in higlass_config:
            if cmp_fileformat(self.pf(pf_uuid).file_forma, hgcf['file_format']):
                if hgcf['extra']:
                    extra_file_key = self.file_key(pf_uuid=pf_uuid, secondary_format=hgcf['extra'])
                    if extra_file_key:
                        higlass_uid = register_to_higlass(self.tibanna_settings,
                                                          self.bucket(argname),
                                                          extra_file_key,
                                                          hgcf['file_type'],
                                                          hgcf['data_type'],
                                                          self.genome_assembly(pf_uuid))
                        break
                else:
                    higlass_uid = register_to_higlass(self.tibanna_settings,
                                                      self.bucket(argname),
                                                      self.file_key(pf_uuid=pf_uuid),
                                                      hgcf['file_type'],
                                                      hgcf['data_type'],
                                                      self.genome_assembly(pf_uuid))
                    break
        if higlass_uid:
            # update the class object
            self.pf(pf_uuid).higlass_uid = higlass_uid
            # prepare for fourfront patch
            self.add_to_pf_patch(pf_uuid, 'higlass_uid')


# TODO: refactor this to inherit from an abstrat class called Runner
# then implement for SBG as well
class Awsem(object):
    '''class that collects Awsem output and metadata information'''
    def __init__(self, json):
        self.args = json['args']
        self.config = json['config']
        self.output_s3 = self.args['output_S3_bucket']
        self.app_name = self.args['app_name']
        self.output_files_meta = json['ff_meta']['output_files']
        self.output_info = None
        if isinstance(json.get('postrunjson'), dict):
            self.output_info = json['postrunjson']['Job']['Output']['Output files']

    def output_type(self, wf_arg_name):
        for x in self.output_files_meta:
            if x['workflow_argument_name'] == wf_arg_name:
                return x['type']
        return None

    def get_md5_filesize_from_output_info(self, argname):
        if self.output_info:
            md5 = self.output_info[argname].get('md5sum', None)
            filesize = self.output_info[argname].get('size', None)
            return (md5, filesize)
        return (None, None)

    def output_files(self):
        files = []
        for argname, key in iter(self.args.get('output_target').items()):
            md5, filesize = self.get_md5_filesize_from_output_info(argname)
            wff = AwsemFile(self.output_s3, key, self,
                            argument_type=self.output_type(argname),
                            filesize=filesize, md5=md5, argument_name=argname)
            files.append(wff)
        return files

    def get_md5_filesize_from_secondary_file_output_info(self, argname, key):
        if self.output_info and 'secondaryFiles' in self.output_info[argname]:
            for sf in self.output_info[argname]['secondaryFiles']:
                if sf.get('target', '') == key:
                    md5 = sf.get('md5sum', None)
                    filesize = sf.get('size', None)
                    return (md5, filesize)
        return (None, None)

    def get_secondary_file_format_from_ff_meta(self, argname, key):
        for pf in self.output_files_meta:
            if pf['workflow_argument_name'] == argname and 'extra_files' in pf:
                for pfextra in pf['extra_files']:
                    if pfextra['upload_key'] == key:
                        return parse_formatstr(pfextra['file_format'])
        return None

    def secondary_output_files(self):
        files = []
        for argname, keylist in iter(self.args.get('secondary_output_target').items()):
            if not isinstance(keylist, list):
                keylist = [keylist]
            for key in keylist:
                md5, filesize = self.get_md5_filesize_from_secondary_file_output_info(argname, key)
                file_format = self.get_secondary_file_format_from_ff_meta(argname, key)
                wff = AwsemFile(self.output_s3, key, self,
                                argument_type=self.output_type(argname),
                                filesize=filesize, md5=md5,
                                format_if_extra=file_format,
                                argument_name=argname)
                files.append(wff)
        return files

    def input_files(self):
        files = []
        for arg_name, item in iter(self.args.get('input_files').items()):
            wff = AwsemFile(item.get('bucket_name'),
                            item.get('object_key'),
                            self,
                            argument_type="Input file",
                            format_if_extra=item.get('format_if_extra', ''),
                            argument_name=arg_name)
            files.append(wff)
        return files

    def all_files(self):
        files = []
        files.extend(self.input_files())
        files.extend(self.output_files())
        return files

    def get_format_if_extras(self, argname):
        format_if_extras = []
        for v in self.input_files():
            if argname == v.argument_name:
                format_if_extras.append(v.format_if_extra)
        return format_if_extras

    def get_file_accessions(self, argname):
        accessions = []
        for v in self.all_files():
            if argname == v.argument_name:
                accessions.append(v.accession)
        return accessions

    def get_file_key(self, argname):
        keys = []
        for v in self.all_files():
            if argname == v.argument_name:
                keys.append(v.key)
        return keys


def post_random_file(bucket, ff_key,
                     file_format='pairs', extra_file_format='pairs_px2',
                     file_extension='pairs.gz', extra_file_extension='pairs.gz.px2',
                     schema='file_processed', extra_status=None):
    """Generates a fake file with random uuid and accession
    and posts it to fourfront. The content is unique since it contains
    its own uuid. The file metadata does not contain md5sum or
    content_md5sum.
    Uses the given fourfront keys
    """
    uuid = str(uuid4())
    accession = generate_rand_accession()
    newfile = {
      "accession": accession,
      "file_format": file_format,
      "award": "b0b9c607-f8b4-4f02-93f4-9895b461334b",
      "lab": "828cd4fe-ebb0-4b36-a94a-d2e3a36cc989",
      "uuid": uuid
    }
    upload_key = uuid + '/' + accession + '.' + file_extension
    tmpfilename = 'alsjekvjf'
    with gzip.open(tmpfilename, 'wb') as f:
        f.write(uuid.encode('utf-8'))
    s3 = boto3.resource('s3')
    s3.meta.client.upload_file(tmpfilename, bucket, upload_key)

    # extra file
    if extra_file_format:
        newfile["extra_files"] = [
            {
               "file_format": extra_file_format,
               "accession": accession,
               "uuid": uuid
            }
        ]
        if extra_status:
            newfile["extra_files"][0]['status'] = extra_status
        extra_upload_key = uuid + '/' + accession + '.' + extra_file_extension
        extra_tmpfilename = 'alsjekvjf-extra'
        with open(extra_tmpfilename, 'w') as f:
            f.write(uuid + extra_file_extension)
        s3.meta.client.upload_file(extra_tmpfilename, bucket, extra_upload_key)
    response = post_metadata(newfile, schema, key=ff_key)
    print(response)
    return newfile


def register_to_higlass(tbn, bucket, key, filetype, datatype, genome_assembly=None):
    if not genome_assembly:
        return None
    payload = {"filepath": bucket + "/" + key,
               "filetype": filetype, "datatype": datatype,
               "coordSystem": genome_assembly}
    higlass_keys = tbn.s3.get_higlass_key()
    if not isinstance(higlass_keys, dict):
        raise Exception("Bad higlass keys found: %s" % higlass_keys)
    auth = (higlass_keys['key'], higlass_keys['secret'])
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}
    res = requests.post(higlass_keys['server'] + '/api/v1/link_tile/',
                        data=json.dumps(payload), auth=auth, headers=headers)
    printlog("LOG resiter_to_higlass(POST request response): " + str(res.json()))
    return res.json()['uuid']


def cmp_fileformat(format1, format2):
    return parse_formatstr(format1) == parse_formatstr(format2)
