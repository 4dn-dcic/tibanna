import boto3
import json
from datetime import datetime, timedelta
from collections import OrderedDict
from dcicutils import ff_utils


class FourfrontFile(object):
    def __init__(self, uuid, size=None):
        self.uuid = uuid
        self.size = size


class FourfrontWorkflowRunTracing(object):
    def __init__(self, final_pf_uuid, key):
        self.key = key
        self.final_pf = self.fourfront_file(final_pf_uuid)
        self.steps = []
        self.trace(self.final_pf)

    def trace_wfr_forward(self, pf_uuid):
        res = ff_utils.get_metadata(pf_uuid, key=self.key)
        wfr = res['workflow_run_inputs'][0]['uuid']
        return wfr
        
    def trace_wfr_backward(self, pf_uuid):
        res = ff_utils.get_metadata(pf_uuid, key=self.key)
        if 'workflow_run_outputs' not in res or not res['workflow_run_outputs']:
            return None, None
        wfr_uuid = res['workflow_run_outputs'][0]['uuid']
        input_files = []
        for ip in res['workflow_run_outputs'][0]['input_files']:
            if ip['value']['@type'][0] != 'FileReference':
                input_files.append(self.fourfront_file(ip['value']['uuid']))
        return (wfr_uuid, input_files)

    def trace(self, final_pf, reverse_step_id=0):
        wfr_uuid, input_files = self.trace_wfr_backward(final_pf.uuid)
        if wfr_uuid:
            if not self.wfr_exists(wfr_uuid):
                self.steps.append(Step(reverse_step_id, wfr_uuid, input_files, final_pf, key=self.key))
                for ip in input_files:
                    self.trace(ip, reverse_step_id + 1)

    def fourfront_file(self, file_uuid):
        return FourfrontFile(file_uuid, self.file_size(file_uuid))

    def file_size(self, file_uuid):
        return ff_utils.get_metadata(file_uuid, key=self.key)['file_size']

    def wfr_exists(self, wfr_uuid):
        for s in self.steps:
            if s.wfr.uuid == wfr_uuid:
                return True
        return False

    @property
    def cost(self):
        sumcost = 0
        for s in self.steps:
            sumcost += s.wfr.metrics['cost']
        return sumcost

    @property
    def runtime_min(self):
        total_runtime = 0
        for s in self.steps:
            total_runtime += s.wfr.metrics['runtime_MIN']
        return total_runtime

    @property
    def runtime_hr(self):
        return self.runtime_min / 60

    @property
    def step_cost(self):
        stepcost = dict()
        for s in self.steps:
            if s.wfr.workflow not in stepcost:
                stepcost[s.wfr.workflow] = 0
            stepcost[s.wfr.workflow] += s.wfr.metrics['cost']
        return stepcost

    @property
    def step_runtime_hr(self):
        stepruntime = dict()
        for s in self.steps:
            if s.wfr.workflow not in stepruntime:
                stepruntime[s.wfr.workflow] = 0
            stepruntime[s.wfr.workflow] += s.wfr.metrics['runtime_MIN'] / 60
        return stepruntime
        


class Step(object):
    def __init__(self, reverse_step_id, wfr, input_files, output_file, key):
        self.reverse_step_id = reverse_step_id
        self.wfr = WorkflowRun(wfr, key=key)
        self.input_files = input_files
        self.output_file = output_file


class WorkflowRun(object):
    def __init__(self, wfr_uuid, key):
        wfr_meta = ff_utils.get_metadata(wfr_uuid, key=key)
        self.uuid = wfr_uuid
        self.workflow = wfr_meta['workflow']['title']
        s = wfr_meta['awsem_postrun_json']
        awsem_job_id = postrun_json_url_to_job_id(s)
        self.metrics = get_metrics(job_id=awsem_job_id, key=key, wf_category=None)



def postrun_json_url_to_job_id(s):
    return str(s.split('/')[-1].split('.')[0])


def get_metrics(exec_arn=None, job_id=None, logbucket='tibanna-output', key=None, wf_category='repliseq_parta'):
    '''take either awsem jobid and returns benchmark dictionary object.
    key is either keydata or keydev
    wf_category determines what kind of additional parameters to add.
    '''
    if not exec_arn and not job_id:
        raise Exception("Either exec_arn or job_id must be provided")
    if exec_arn and job_id:
        raise Exception("Use either exec_arn or job_id, not both.")
    if exec_arn:
        desc = boto3.client('stepfunctions').describe_execution(executionArn=exec_arn)
        job_id = str(json.loads(desc['input'])['jobid'])
    s3 = boto3.client('s3')
    r = s3.get_object(Bucket=logbucket, Key='%s.postrun.json' % job_id)
    d = json.loads(r['Body'].read())
    metrics = d['Job']['Metrics']
    runtime = run_time(d)
    cost = get_cost(d)
    metrics.update({"runtime_MIN": runtime, "cost": cost})
    return metrics


def add_additional_parameters(d, category='repliseq_parta', key=None):
    '''returns a dictionary that serves as additional parameters
    input d is the dictionary object of the postrun json
    '''
    if category == 'repliseq_parta':
        if not key:
            return {}
        fastq_uuid = d['Job']['Input']['Input_files_data']['fastq']['path'].split('/')[0]
        return get_additional_parameters_for_repliseq_parta(fastq_uuid, key)
    else:
        return {}  # until we have a new category


def get_file_size(argdict):
    if argdict.get('size', 0):
        return argdict['size']
    s3 = boto3.client('s3')
    return s3.get_object(Bucket=argdict['dir'], Key=argdict['path'])['ContentLength']


def run_time(d):
    '''Input d is the dictionary form of the postrun json.
    returns runtime in total minutes.'''
    t1 = d['Job']['start_time']
    t2 = d['Job']['end_time']
    t1_dt = datetime.strptime(t1, '%Y%m%d-%H:%M:%S-UTC')
    t2_dt = datetime.strptime(t2, '%Y%m%d-%H:%M:%S-UTC')
    td = t2_dt - t1_dt
    return td.total_seconds() / 60


def get_cost(d):
    '''Input d is the dictionary form of the postrun json'''
    def reformat_time(t, delta):
        d = datetime.strptime(t, '%Y%m%d-%H:%M:%S-UTC') + timedelta(days=delta)
        return d.strftime("%Y-%m-%d")
    start_time = reformat_time(d['Job']['start_time'], -1)  # give more room
    end_time = reformat_time(d['Job']['end_time'], 1)  # give more room
    awsem_job_id = d['Job']['JOBID']
    billing_args = {'Filter': {'Tags': {'Key': 'Name', 'Values': ['awsem-' + awsem_job_id]}},
                    'Granularity': 'DAILY',
                    'TimePeriod': {'Start': start_time, 'End': end_time},
                    'Metrics': ['BlendedCost']}
    billingres = boto3.client('ce').get_cost_and_usage(**billing_args)
    return sum([float(_['Total']['BlendedCost']['Amount']) for _ in billingres['ResultsByTime']])


def collect_metrics(search_res, outfilename, key=None):
    print("total %d entries" % len(search_res))
    all_metrics = []
    for r in search_res:
        s = r['awsem_postrun_json']
        awsem_job_id = postrun_json_url_to_job_id(s)
        m = get_metrics(awsem_job_id, key=key)
        print(m)  # debugging
        all_metrics.append(m)
    with open(outfilename, 'w') as f:
        json.dump(all_metrics, f,  indent=4)


def get_additional_parameters_for_repliseq_parta(fastq_uuid, key):
    fastq_metadata = ff_utils.get_metadata(fastq_uuid, key=key)
    species = get_species(fastq_metadata)
    exp_type = get_experiment_type(fastq_metadata)
    return dict(species=species, exp_type=exp_type)


def get_species(fastq_metadata):
    try:
        return fastq_metadata['experiments'][0]['biosample']['biosource'][0]['individual']['organism']['name']
    except:
        return ''


def get_experiment_type(fastq_metadata):
    try:
        return fastq_metadata['experiments'][0]['experiment_type']
    except:
        return ''
