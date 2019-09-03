import boto3
import gzip
from uuid import uuid4
from dcicutils.ff_utils import (
    get_metadata,
    post_metadata,
    generate_rand_accession,
)
from tibanna.nnested_array import (
    flatten,
)
from .vars import (
    DEFAULT_AWARD,
    DEFAULT_LAB,
    ACCESSION_PREFIX,
    HIGLASS_BUCKETS
)
from tibanna_ffcommon.portal_utils import (
    WorkflowRunMetadataAbstract,
    ProcessedFileMetadataAbstract,
    FourfrontUpdaterAbstract,
    FFInputAbstract
)


class PonyInput(FFInputAbstract):
    pass


class WorkflowRunMetadata(WorkflowRunMetadataAbstract):
    '''
    fourfront metadata
    '''

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.award = kwargs.get('award', DEFAULT_AWARD)
        self.lab = kwargs.get('lab', DEFAULT_LAB)


class ProcessedFileMetadata(ProcessedFileMetadataAbstract):

    accession_prefix = ACCESSION_PREFIX

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.award = kwargs.get('award', DEFAULT_AWARD)
        self.lab = kwargs.get('lab', DEFAULT_LAB)
        self.source_experiments = kwargs.get('source_experiments', None)

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
            ff_keys = self.s3.get_access_keys('access_key_tibanna')
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


class QCArgumentInfo(SerializableObject):
    def __init__(self, argument_type, workflow_argument_name, argument_to_be_attached_to, qc_type,
                 qc_zipped=False, qc_html=False, qc_json=False, qc_table=False,
                 qc_zipped_html=None, qc_zipped_tables=None):
        if argument_type != 'Output QC file':
            raise Exception("QCArgument it not Output QC file: %s" % argument_type)
        self.workflow_argument_name = workflow_argument_name
        self.argument_to_be_attached_to = argument_to_be_attached_to
        self.qc_type = qc_type
        self.qc_zipped = qc_zipped
        self.qc_html = qc_html
        self.qc_json = qc_json
        self.qc_table = qc_table
        self.qc_zipped_html = qc_zipped_html
        self.qc_zipped_tables = qc_zipped_tables


class InputExtraArgumentInfo(SerializableObject):
    def __init__(self, argument_type, workflow_argument_name, argument_to_be_attached_to, **kwargs):
        if argument_type != 'Output to-be-extra-input file':
            raise Exception("InputExtraArgumentInfo is not Output to-be-extra-input file: %s" % argument_type)
        self.workflow_argument_name = workflow_argument_name
        self.argument_to_be_attached_to = argument_to_be_attached_to


class FourfrontUpdater(object):
    """This class integrates three different sources of information:
    postrunjson, workflowrun, processed_files,
    and does the final updates necessary"""

    WorkflowRunMetadata = WorkflowRunMetadata
    ProcessedFileMetadata = ProcessedFileMetadata
    default_email_sender = '4dndcic@gmail.com' 
    higlass_buckets =  HIGLASS_BUCKETS

    def __init__(self, **kwargs):
        super().__init__(**kwargs):

    def create_qc_template(self):
        res = super().create_qc_template()
        res.update({"award": DEFAULT_AWARD,
                    "lab": DEFAULT_LAB})
        return res


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
    accession = generate_rand_accession(ACCESSION_PREFIX, 'FI')
    newfile = {
      "accession": accession,
      "file_format": file_format,
      "award": DEFAULT_AWARD,
      "lab": DEFAULT_LAB,
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
