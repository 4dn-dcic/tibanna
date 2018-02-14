import boto3
import wranglertools.fdnDCIC as fdnDCIC
import json
from core.utils import run_workflow as _run_workflow
import datetime
import time
import os


def prep_awsem_template(filename, webprod=False, tag=None):
    Tibanna_dir=os.path.dirname(os.path.realpath(__file__)).replace('/core', '')
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


def prep_input_file_entry_list_for_single_exp(prev_workflow_title, prev_output_argument_name, connection,
                                              addon=None, wfuuid=None):
    schema_name = 'search/?type=WorkflowRunAwsem&workflow.title=' + prev_workflow_title + '&run_status=complete'
    response = fdnDCIC.get_FDN(schema_name, connection)
    files_for_ep = map_exp_to_inputfile_entry(response, prev_output_argument_name, connection,
                                              addon=addon, wfuuid=wfuuid)
    return(files_for_ep)


def prep_input_file_entry_list_for_merging_expset(prev_workflow_title, prev_output_argument_name, connection,
                                                  addon=None, wfuuid=None):
    files_for_ep = prep_input_file_entry_list_for_single_exp(prev_workflow_title,
                                                             prev_output_argument_name,
                                                             connection, addon, wfuuid)
    ep_lists_per_eps = map_expset_to_allexp(files_for_ep.keys(), connection)
    input_files_list = map_expset_to_inputfile_list(ep_lists_per_eps, files_for_ep)
    return(input_files_list)


def create_inputfile_entry(file_uuid, connection, addon=None, wfr_input_filter=None):
    """create an input file entry (uuid, accession, object_key)
    addon : list of following strings (currently only 're' is available to add restriction enzyme info)
    wfr_input_filter : workflow_uuid, return None if specified and has a completed or
    started run of the specified workflow
    assumes file is a processed file (has source_experiments field)
    assumes single source_experiments
    """
    file_dict = fdnDCIC.get_FDN(file_uuid, connection)
    if 'source_experiments' not in file_dict:
        return(None)
    sep = file_dict['source_experiments'][0]
    sep_dict = fdnDCIC.get_FDN(sep, connection)
    sep_id = sep_dict['@id']
    entry = {'uuid': file_dict['uuid'], 'accession': file_dict['accession'],
             'object_key': file_dict['upload_key'].replace(file_dict['uuid']+'/', ''),
             'source_experiments': [sep_id]}
    if addon:
        if 're' in addon:
            entry['RE'] = get_digestion_enzyme_for_expr(sep, connection)

    if wfr_input_filter:
        skip = False
        wfr_info = get_info_on_workflowrun_as_input(file_dict, connection)
        if wfr_input_filter in wfr_info:
            if 'complete' in wfr_info[wfr_input_filter]:
                skip = True
            if 'started' in wfr_info[wfr_input_filter]:
                skip = True
        if skip:
            return(None)

    return(entry)


def get_info_on_workflowrun_as_input(file_dict, connection):
    """given a json for file, returns a dictionary with workflow uuids as keys.
    dictionary structure : dict{wf_uuid}{run_status} = [wfr_id1, wfr_id2, ... ]
    These workflow uuids are the the ones in the workflow runs
    that has the given file as input
    """
    wfr_info = dict()
    if 'workflow_run_inputs' in file_dict:
        wfr_list = file_dict.get("workflow_run_inputs")
        if wfr_list:
            for wfr in wfr_list:
                wfr_dict = fdnDCIC.get_FDN(wfr, connection)
                wf = wfr_dict['workflow'].replace('/workflows/', '').replace('/', '')
                run_status = wfr_dict['run_status']
                if wf not in wfr_info:
                   wfr_info[wf] = dict()
                if run_status not in wfr_info[wf]:
                    wfr_info[wf][run_status] = []
                wfr_info[wf][run_status].append(wfr)
    return(wfr_info)


def map_exp_to_inputfile_entry(wfr_search_response, prev_output_argument_name, connection, addon=None, wfuuid=None):
    """single-experiment (id not uuid) -> one output file entry (uuid, accession, object_key)
    addon : list of following strings (currently only 're' is available to add restriction enzyme info)
    """
    files_for_ep = dict()
    for entry in wfr_search_response['@graph']:
        for of in entry['output_files']:
            if of['workflow_argument_name'] == prev_output_argument_name:
                file_uuid = of['value']
                break
        print(file_uuid)
        file_entry = create_inputfile_entry(file_uuid, connection, addon=addon, wfr_input_filter=wfuuid)
        if file_entry:
            if 'source_experiments' in file_entry and file_entry['source_experiments']:
                sep_id = file_entry['source_experiments'][0]
                files_for_ep[sep_id] = file_entry
    return(files_for_ep)


def get_expset_from_exp(expr, connection):
    """getting the experiment sets of an experiment
    """
    sep_dict = fdnDCIC.get_FDN(expr, connection)
    seps = sep_dict['experiment_sets']
    return(seps)


def get_allexp_from_expset(expset, connection):
    """getting all the experiments from an experiment set
    """
    seps_dict = fdnDCIC.get_FDN(expset, connection)
    return(seps_dict['experiments_in_set'])


def map_expset_to_allexp(exp_list, connection):
    """map of experiment set -> all experiments, for all experiments given
    This function could be useful for a workflow that requires merging
    all experiments in an experiment set.
    Only the first listed experiment set of a given experiment is used.
    """
    ep_lists_per_eps = dict()
    for sep_id in exp_list:
        seps = get_expset_from_exp(sep_id, connection)[0]
        ep_lists_per_eps[seps] = get_allexp_from_expset(seps, connection)
    return(ep_lists_per_eps)


def merge_input_file_entry_list_for_exp_list(explist, files_for_ep):
    input_files = dict()
    keylist = ['uuid', 'accession', 'object_key']
    for k in keylist:
        input_files[k] = []
    for ep in explist:
        if ep in files_for_ep:
            for k in keylist:
                input_files[k].append(files_for_ep[ep][k])
    return(input_files)


def map_expset_to_inputfile_list(ep_lists_per_eps, files_for_ep):
    """input_pairs_files is a list of input pairs files lists.
    This function could be useful for a workflow that requires merging
    all experiments in an experiment set.
    """
    input_files_list = dict()
    for eps in ep_lists_per_eps:
        input_files = merge_input_file_entry_list_for_exp_list(ep_lists_per_eps[eps], files_for_ep)
        # include only the set that's full (e.g. if only 3 out of 4 exp has an output, do not include)
        if len(ep_lists_per_eps[eps]) == len(input_files):
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
        wfuuid='c9e0e6f7-b0ed-4a42-9466-cadc2dd84df0',
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
                                                                     connection,
                                                                     wfuuid=wfuuid)
    if input_files_list: 
        for _, entry in input_files_list.iteritems():
            print(entry)
            awsem_json = create_awsem_json_for_workflowrun(entry, awsem_template_json, input_argument_name,
                                                           awsem_tag=awsem_tag,
                                                           parameters_to_override=parameters_to_override,
                                                           parameters_to_delete=parameters_to_delete,
                                                           webprod=webprod)
            resp = _run_workflow(awsem_json, workflow=stepfunction_workflow)
            print(resp)
    return({'input_files_list': input_files_list})


def collect_pairs_files_to_run_pairsqc(
        keypairs_file,
        webprod=True,
        wfuuid='ae3a87cb-3fa2-469e-97c7-540fc2d0a117',
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
                                                                 connection,
                                                                 wfuuid=wfuuid)
    if input_files_list:
        for _, entry in input_files_list.iteritems():
            parameters_to_override = {'sample_name': entry['accession'], 'enzyme': re_cutter[entry['RE']]}
            awsem_json = create_awsem_json_for_workflowrun(entry, awsem_template_json, input_argument_name,
                                                           awsem_tag=awsem_tag,
                                                           parameters_to_override=parameters_to_override,
                                                           parameters_to_delete=parameters_to_delete,
                                                           webprod=webprod)
            resp = _run_workflow(awsem_json, workflow=stepfunction_workflow)
            print(resp)
    return({'input_files_list': input_files_list})
