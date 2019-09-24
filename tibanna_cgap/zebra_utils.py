import boto3
import gzip
from uuid import uuid4
from tibanna.utils import printlog
from dcicutils.ff_utils import (
    get_metadata,
    post_metadata,
    generate_rand_accession,
)
from tibanna.nnested_array import (
    flatten,
)
from .vars import (
    DEFAULT_PROJECT,
    DEFAULT_INSTITUTION,
    ACCESSION_PREFIX,
    HIGLASS_BUCKETS
)
from tibanna_ffcommon.portal_utils import (
    WorkflowRunMetadataAbstract,
    ProcessedFileMetadataAbstract,
    FourfrontStarterAbstract,
    FourfrontUpdaterAbstract,
    FFInputAbstract,
    aslist
)
from tibanna_ffcommon.exceptions import (
    FdnConnectionException
)


class ZebraInput(FFInputAbstract):
    pass


class WorkflowRunMetadata(WorkflowRunMetadataAbstract):
    '''
    fourfront metadata
    '''

    def __init__(self, **kwargs):
        self.institution = kwargs.get('institution', DEFAULT_INSTITUTION)
        self.project = kwargs.get('project', DEFAULT_PROJECT)
        super().__init__(**kwargs)


class ProcessedFileMetadata(ProcessedFileMetadataAbstract):

    accession_prefix = ACCESSION_PREFIX

    def __init__(self, **kwargs):
        self.institution = kwargs.get('institution', DEFAULT_INSTITUTION)
        self.project = kwargs.get('project', DEFAULT_PROJECT)
        self.source_samples = kwargs.get('source_samples', None)
        super().__init__(**kwargs)


class FourfrontStarter(FourfrontStarterAbstract):

    InputClass = ZebraInput
    ProcessedFileMetadata = ProcessedFileMetadata
    WorkflowRunMetadata = WorkflowRunMetadata

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.source_samples_ = None

    def pf(self, argname):
        return super().pf(argname, source_samples=self.source_samples)

    def get_source_sample(self, input_file_uuid):
        """
        Connects to fourfront and get source experiment info as a unique list
        Takes a single input file uuid.
        """
        pf_source_samples_set = set()
        inf_uuids = aslist(flatten(input_file_uuid))
        for inf_uuid in inf_uuids:
            infile_meta = get_metadata(inf_uuid,
                                       key=self.tbn.ff_keys,
                                       ff_env=self.tbn.env,
                                       add_on='frame=object')
            if infile_meta.get('samples'):
                for exp in infile_meta.get('samples'):
                    exp_obj = get_metadata(exp,
                                           key=self.tbn.ff_keys,
                                           ff_env=self.tbn.env,
                                           add_on='frame=raw')
                    pf_source_samples_set.add(exp_obj['uuid'])
            if infile_meta.get('source_samples'):
                # this field is an array of strings, not linkTo's
                pf_source_samples_set.update(infile_meta.get('source_samples'))
        return list(pf_source_samples_set)

    def merge_source_samples(self):
        """
        Connects to fourfront and get source experiment info as a unique list
        Takes a list of input file uuids.
        """
        pf_source_samples = set()
        for input_file_uuid in self.inp.input_file_uuids:
            pf_source_samples.update(self.get_source_sample(input_file_uuid))
        return list(pf_source_samples)

    @property
    def source_samples(self):
        if self.source_samples_:
            return self.source_samples_
        else:
            self.source_samples_ = self.merge_source_samples()
            return self.source_samples_


class FourfrontUpdater(FourfrontUpdaterAbstract):
    """This class integrates three different sources of information:
    postrunjson, workflowrun, processed_files,
    and does the final updates necessary"""

    WorkflowRunMetadata = WorkflowRunMetadata
    ProcessedFileMetadata = ProcessedFileMetadata
    default_email_sender = 'cgap.everyone@gmail.com'
    higlass_buckets = HIGLASS_BUCKETS

    def create_qc_template(self):
        res = super().create_qc_template()
        res.update({"institution": DEFAULT_INSTITUTION,
                    "project": DEFAULT_PROJECT})
        return res

    def patch_qc(self, qc_target_accession, qc_uuid, qc_type):
        try:
            res = get_metadata(qc_target_accession,
                               key=self.tibanna_settings.ff_keys,
                               ff_env=self.tibanna_settings.env,
                               add_on='frame=object',
                               check_queue=True)
        except Exception as e:
            raise FdnConnectionException(e)
        if 'quality_metric' not in res:  # first qc metric for this file
            super().patch_qc(qc_target_accession, qc_uuid)
        else:
            existing_qctype = res['quality_metric'].split('/')[1].replace('-', '_'). \
                              replace('quality_metrics', 'quality_metric')
            existing_qc_uuid = res['quality_metric'].split('/')[2]
            printlog("existing qc=" + res['quality_metric'] + ' ' + existing_qctype)
            printlog("new qc=" + qc_uuid + ' ' + qc_type)
            if existing_qctype == qc_type:  # if existing qc metric is of the same type, overwrite.
                super().patch_qc(qc_target_accession, qc_uuid)
            elif existing_qctype == 'quality_metric_qclist':
                # we assume that the same qc type occurs only once per qc list
                # and so a new workflow run can update the one with the same qc type
                existing_qc_meta = get_metadata(existing_qc_uuid,
                                                key=self.tibanna_settings.ff_keys,
                                                ff_env=self.tibanna_settings.env,
                                                add_on='frame=object',
                                                check_queue=True)
                if qc_type not in [qc['qc_type'] for qc in existing_qc_meta['qc_list']]:
                    existing_qc_meta['qc_list'].append({'qc_type': qc_type, 'value': qc_uuid})
                    self.update_patch_items(existing_qc_meta['uuid'], {'qc_list': existing_qc_meta['qc_list']})
                else:
                    for i, qc in enumerate(existing_qc_meta['qc_list']):
                        if qc['qc_type'] == qc_type:
                            existing_qc_meta['qc_list'][i]['value'] = qc_uuid
                            break
                    self.update_patch_items(existing_qc_meta['uuid'], {'qc_list': existing_qc_meta['qc_list']})
            else:
                # new qc type is being added - create a qc list and move the existing qc to the qc list and
                # add the new one to the qc list
                new_qclist_object = self.create_qc_template()
                new_qclist_object['qc_list'] = [{'qc_type': existing_qctype, 'value': existing_qc_uuid},
                                                {'qc_type': qc_type, 'value': qc_uuid}]
                self.update_post_items(new_qclist_object['uuid'], new_qclist_object, 'quality_metric_qclist')
                super().patch_qc(qc_target_accession, new_qclist_object['uuid'])


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
      "institution": DEFAULT_INSTITUTION,
      "project": DEFAULT_PROJECT,
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
