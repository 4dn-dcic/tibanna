import boto3
import wranglertools.fdnDCIC as fdnDCIC
import json
from core.utils import run_workflow as _run_workflow
import datetime
import time
import os


def prep_awsem_template(filename, webprod=False, tag=None,
                        Tibanna_dir=os.path.dirname(os.path.realpath(__file__))):
    template = Tibanna_dir + '/test_json/' + filename
    with open(template, 'r') as f:
        awsem_template = json.load(f)
    # webdev ->webprod
    if webprod:
        awsem_template['output_bucket'] = 'elasticbeanstalk-fourfront-webprod-wfoutput'
        awsem_template['_tibanna']['env'] = 'fourfront-webprod'
        for inb in awsem_template['input_files']:
            inb['bucket_name'] = inb['bucket_name'].replace('webdev', 'webprod')
    if tag:
        awsem_template['tag'] = tag
        clear_awsem_template(awsem_template)
    return awsem_template


def clear_awsem_template(awsem_template):
    """clear awsem template for reuse"""
    if 'response' in awsem_template['_tibanna']:
        del(awsem_template['_tibanna']['response'])
    if 'run_name' in awsem_template['_tibanna'] and len(awsem_template['_tibanna']['run_name']) > 50:
        awsem_template['_tibanna']['run_name'] = awsem_template['_tibanna']['run_name'][:-36]


def get_species_from_expr(expr, connection):
    """get species for a given experiment"""
    sep_resp = fdnDCIC.get_FDN(expr, connection)
    sep_resp2 = fdnDCIC.get_FDN(sep_resp["biosample"], connection)["biosource"]
    indv = fdnDCIC.get_FDN(sep_resp2[0], connection)["individual"]
    return(str(fdnDCIC.get_FDN(indv, connection)['organism']))


def get_digestion_enzyme_for_expr(expr, connection):
    """get species for a given experiment
    Returns enzyme name (e.g. HindIII)
    """
    exp_resp = fdnDCIC.get_FDN(expr, connection)
    re = exp_resp['digestion_enzyme'].replace('/enzymes/', '').replace('/', '')
    return(re)


def rerun(exec_arn, workflow='tibanna_pony'):
    """rerun a specific job"""
    client = boto3.client('stepfunctions')
    res = client.describe_execution(executionArn=exec_arn)
    awsem_template = json.loads(res['input'])
    clear_awsem_template(awsem_template)
    return(_run_workflow(awsem_template, workflow=workflow))


def rerun_many(workflow='tibanna_pony', stopdate='13Feb2018', stophour=13,
               stopminute=0, offset=5, sleeptime=5, status='FAILED',
               region='us-east-1', acc='643366669028'):
    """Reruns step function jobs that failed after a given time point (stopdate, stophour (24-hour format), stopminute)
    By default, stophour is in EST. This can be changed by setting a different offset (default 5)
    Sleeptime is sleep time in seconds between rerun submissions.
    By default, it reruns only 'FAILED' runs, but this can be changed by resetting status.
    examples)
    rerun_many('tibanna_pony-dev')
    rerun_many('tibanna_pony', stopdate= '14Feb2018', stophour=14, stopminute=20)
    """
    stophour = stophour + offset
    stoptime_in_datetime = datetime.datetime.strptime(stopdate + ' ' + str(stophour) + ':' + str(stopminute),
                                                      '%d%b%Y %H:%M')
    client = boto3.client('stepfunctions')
    stateMachineArn = 'arn:aws:states:' + region + ':' + acc + ':stateMachine:' + workflow
    sflist = client.list_executions(stateMachineArn=stateMachineArn, statusFilter=status)
    k = 0
    for exc in sflist['executions']:
        if exc['stopDate'].replace(tzinfo=None) > stoptime_in_datetime:
            k = k + 1
            rerun(exc['executionArn'], workflow=workflow)
            time.sleep(sleeptime)


def kill_all(workflow='tibanna_pony', region='us-east-1', acc='643366669028'):
    """killing all the running jobs"""
    client = boto3.client('stepfunctions')
    stateMachineArn = 'arn:aws:states:' + region + ':' + acc + ':stateMachine:' + workflow
    sflist = client.list_executions(stateMachineArn=stateMachineArn, statusFilter='RUNNING')
    for exc in sflist['executions']:
        client.stop_execution(executionArn=exc['executionArn'], error="Aborted")


def get_connection(keypairs_file):
    key = fdnDCIC.FDN_Key(keypairs_file, "default")
    connection = fdnDCIC.FDN_Connection(key)
    return(connection)


def prep_input_file_entry_list_for_single_exp(prev_workflow_title, prev_output_argument_name, connection):
    schema_name = 'search/?type=WorkflowRunAwsem&workflow.title=' + prev_workflow_title + '&run_status=complete'
    response = fdnDCIC.get_FDN(schema_name, connection)
    files_for_ep = map_exp_to_inputfile_entry(response, prev_output_argument_name, connection)
    return(files_for_ep)


def prep_input_file_entry_list_for_merging_expset(prev_workflow_title, prev_output_argument_name, connection):
    files_for_ep = prep_input_file_entry_list_for_single_exp(prev_workflow_title,
                                                             prev_output_argument_name,
                                                             connection)
    ep_lists_per_eps = map_expset_to_allexp(files_for_ep.keys(), connection)
    input_files_list = map_expset_to_inputfile_list(ep_lists_per_eps)
    return(input_files_list)


def map_exp_to_inputfile_entry(wfr_search_response, prev_output_argument_name, connection, addon=None):
    """single-experiment (id not uuid) -> one output file entry (uuid, accession, object_key)"""
    files_for_ep = dict()
    for entry in wfr_search_response['@graph']:
        for of in entry['output_files']:
            if of['workflow_argument_name'] == prev_output_argument_name:
                pairs_file = of['value']
                break
        pairs_dict = fdnDCIC.get_FDN(pairs_file, connection)
        sep = pairs_dict['source_experiments'][0]
        sep_dict = fdnDCIC.get_FDN(sep, connection)
        sep_id = sep_dict['@id']
        files_for_ep[sep_id] = {'uuid': pairs_dict['uuid'], 'accession': pairs_dict['accession'],
                                'object_key': pairs_dict['upload_key'].replace(pairs_dict['uuid']+'/', '')}
        if addon:
            if 're' in addon:
                files_for_ep[sep_id]['RE'] = get_digestion_enzyme_for_expr(sep, connection)
    return(files_for_ep)


def map_expset_to_allexp(exp_list, connection):
    """map of experiment set -> all experiments, for all experiments given
    This function could be useful for a workflow that requires merging
    all experiments in an experiment set.
    """
    ep_lists_per_eps = dict()
    for sep_id in exp_list:
        sep_dict = fdnDCIC.get_FDN(sep_id, connection)
        seps = sep_dict['experiment_sets'][0]
        seps_dict = fdnDCIC.get_FDN(seps, connection)
        ep_lists_per_eps[seps] = seps_dict['experiments_in_set']
    return(ep_lists_per_eps)


def map_expset_to_inputfile_list(ep_lists_per_eps, files_for_ep):
    """input_pairs_files is a list of input pairs files lists.
    This function could be useful for a workflow that requires merging
    all experiments in an experiment set.
    """
    input_files_list = dict()
    for eps in ep_lists_per_eps:
        input_files = dict()
        input_files['uuid'] = []
        input_files['accession'] = []
        input_files['object_key'] = []
        skip = False
        for ep in ep_lists_per_eps[eps]:
            if ep in files_for_ep:
                input_files['uuid'].append(files_for_ep[ep]['uuid'])
                input_files['accession'].append(files_for_ep[ep]['accession'])
                input_files['object_key'].append(files_for_ep[ep]['object_key'])
            else:
                skip = True
        # include only the set that's full (e.g. if only 3 out of 4 exp has an output, do not include)
        if not skip:
            input_files_list['eps'] = input_files
    return(input_files_list)


def create_awsem_json_for_workflowrun(input_entry, awsem_template_file, workflow_argname,
                                      awsem_tag=None, parameters_to_override=None,
                                      parameters_to_delete=None, webprod=False):
    awsem_template = prep_awsem_template(awsem_template_file, webprod, tag=awsem_tag)
    for inb in awsem_template['input_files']:
        if inb['workflow_argument_name'] == workflow_argname:
            inb['uuid'] = input_entry['uuid']
            inb['object_key'] = input_entry['object_key']
    if parameters_to_delete:
        for param in parameters_to_delete:
            if param in awsem_template['parameters']:
                del awsem_template['parameters'][param]
    if parameters_to_override:
        for param in parameters_to_override:
            awsem_template['parameters'][param] = parameters_to_override[param]
    return(awsem_template)


def collect_pairs_files_to_run_hi_c_processing_pairs(
        keypairs_file,
        webprod=True,
        prev_workflow_title='Hi-C%20Post-alignment%20Processing',
        prev_output_argument_name='filtered_pairs',
        awsem_template_json='awsem_hicpairs_easy.json',
        input_argument_name='input_pairs',
        awsem_tag="0.2.5",
        parameters_to_override={'maxmem': '32g'},
        parameters_to_delete=['custom_res', 'min_res'],
        stepfunction_workflow='tibanna_pony-dev'):
    """Very high-level function for collecting all legit
    pairs files and run hi-c-processing-pairs.
    It will become more generalized soon.
    """
    connection = get_connection(keypairs_file)
    input_files_list = prep_input_file_entry_list_for_merging_expset(prev_workflow_title,
                                                                     prev_output_argument_name,
                                                                     connection)
    for entry in input_files_list:
        awsem_json = create_awsem_json_for_workflowrun(entry, awsem_template_json, input_argument_name,
                                                       awsem_tag=awsem_tag,
                                                       parameters_to_override=parameters_to_override,
                                                       parameters_to_delete=parameters_to_delete,
                                                       webprod=webprod)
        resp = _run_workflow(awsem_json, workflow=stepfunction_workflow)
        print(resp)


def collect_pairs_files_to_run_pairsqc(
        keypairs_file,
        webprod=True,
        prev_workflow_title='Hi-C%20Post-alignment%20Processing',
        prev_output_argument_name='filtered_pairs',
        awsem_template_json='awsem_pairsqc.json',
        input_argument_name='input_pairs',
        awsem_tag="0.2.5",
        parameters_to_delete=None,
        stepfunction_workflow='tibanna_pony'):
    """Very high-level function for collecting all legit
    pairs files and run hi-c-processing-pairs.
    It will become more generalized soon.
    """
    re_cutter = {'HindIII': '6', 'DpnII': '4', 'MboI': '4', 'NcoI': '6'}
    connection = get_connection(keypairs_file)
    input_files_list = prep_input_file_entry_list_for_single_exp(prev_workflow_title,
                                                                 prev_output_argument_name,
                                                                 connection)
    for entry in input_files_list:
        parameters_to_override = {'sample_name': entry['accession'], 'enzyme': re_cutter[entry['RE']]}
        awsem_json = create_awsem_json_for_workflowrun(entry, awsem_template_json, input_argument_name,
                                                       awsem_tag=awsem_tag,
                                                       parameters_to_override=parameters_to_override,
                                                       parameters_to_delete=parameters_to_delete,
                                                       webprod=webprod)
        resp = _run_workflow(awsem_json, workflow=stepfunction_workflow)
        print(resp)
