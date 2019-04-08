import boto3
import json
from datetime import datetime, timedelta
from collections import OrderedDict
from dcicutils import ff_utils


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
    instance_type = d['config']['instance_type']
    ebs_size = d['config']['ebs_size']
    input_size = dict()
    output_size = dict()
    for argname, argdict in d['Job']['Input']['Input_files_data'].iteritems():
        input_size[argname] = get_file_size(argdict)
    additional_param = dict()
    for argname, argdict in d['Job']['Output']['Output files'].iteritems():
        output_size[argname] = get_file_size(argdict)
    param = d['Job']['Input']['Input_parameters']
    runtime = run_time(d)
    cost = get_cost(d)
    additional_param = add_additional_parameters(d, category=wf_category, key=key)
    run = OrderedDict()
    run['app_name'] = d['Job']['App'].get('App_name', '')
    run['app_version'] = d['Job']['App'].get('App_version', '')
    run['data_size_input'] = input_size
    run['data_size_output'] = output_size
    run['parameters'] = param
    run['additional_parameters'] = additional_param
    metrics.update({"runtime_MIN": runtime})
    run_environment = OrderedDict()
    run_environment['platform'] = "AWS"
    run_environment['executor'] = "tibanna"
    run_environment['instance_type'] = instance_type
    run_environment['ebs_size_GB'] = ebs_size
    job_identification = {"job_id": job_id}
    cost = {"cost_USD": cost}
    final = OrderedDict()
    final['run'] = run
    final['run_environment'] = run_environment
    final['metrics'] = metrics
    final['cost'] = cost
    final['job_identification'] = job_identification
    return final


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
