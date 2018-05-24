from core import ff_utils
from core.utils import run_workflow
from datetime import datetime
import time


# Reference Files
bwa_index = {"human": "4DNFIZQZ39L9",
             "mouse": "4DNFI823LSI8"}

chr_size = {"human": "4DNFI823LSII",
            "mouse": "4DNFI3UBJ3HZ"}

re_nz = {"human": {'MboI': '/files-reference/4DNFI823L812/',
                   'DpnII': '/files-reference/4DNFIBNAPW30/',
                   'HindIII': '/files-reference/4DNFI823MBKE/',
                   'NcoI': '/files-reference/4DNFI3HVU20D/'
                   },
         "mouse": {'MboI': '/files-reference/4DNFI0NK4G14/',
                   'DpnII': '/files-reference/4DNFI3HVC1SE/'}
         }


def extract_file_info(obj_id, arg_name, tibanna, ff):
    raw_bucket = tibanna.s3.raw_file_bucket
    out_bucket = tibanna.s3.outfile_bucket
    """Creates the formatted dictionary for files.
    """
    # start a dictionary
    template = {"workflow_argument_name": arg_name}

    # if it is list of items, change the structure
    if isinstance(obj_id, list):
        object_key = []
        uuid = []
        buckets = []
        for obj in obj_id:
            metadata = ff_utils.get_metadata(obj, connection=ff)
            object_key.append(metadata['display_title'])
            uuid.append(metadata['uuid'])
            # get the bucket
            if 'FileProcessed' in metadata['@type']:
                my_bucket = out_bucket
            else:  # covers cases of FileFastq, FileReference, FileMicroscopy
                my_bucket = raw_bucket
            buckets.append(my_bucket)
        # check bucket consistency
        try:
            assert len(list(set(buckets))) == 1
        except:
            print('Files from different buckets', obj_id)
            return
        template['object_key'] = object_key
        template['uuid'] = uuid
        template['bucket_name'] = buckets[0]
    # if obj_id is a string
    else:
        metadata = ff_utils.get_metadata(obj_id, connection=ff)
        template['object_key'] = metadata['display_title']
        template['uuid'] = metadata['uuid']
        # get the bucket
        if 'FileProcessed' in metadata['@type']:
            my_bucket = out_bucket
        else:  # covers cases of FileFastq, FileReference, FileMicroscopy
            my_bucket = raw_bucket
        template['bucket_name'] = my_bucket
    return template


def run_json(input_files, env, parameters, wf_uuid, wf_name, run_name, tibanna):
    out_bucket = tibanna.s3.outfile_bucket
    """Creates the trigger json that is used by tibanna.
    """
    input_json = {'input_files': input_files,
                  'output_bucket': out_bucket,
                  'workflow_uuid': wf_uuid,
                  "app_name": wf_name,
                  "parameters": parameters,
                  "config": {
                        "ebs_type": "io1",
                        "json_bucket": "4dn-aws-pipeline-run-json",
                        "ebs_iops": 500,
                        "shutdown_min": 30,
                        "s3_access_arn": "arn:aws:iam::643366669028:instance-profile/S3_access",
                        "ami_id": "ami-cfb14bb5",
                        "copy_to_s3": True,
                        "launch_instance": True,
                        "password": "dragonfly",
                        "log_bucket": "tibanna-output",
                        "script_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/",
                        "key_name": "4dn-encode"
                    },
                  "_tibanna": {"env": env,
                               "run_type": wf_name,
                               "run_id": run_name},
                  "tag": '0.2.5'
                  }
    return input_json


def find_pairs(my_rep_set, exclude_miseq, ff, tibanna):
    """Find fastq files from experiment set, exclude miseq.
    """
    report = {}
    rep_resp = my_rep_set['experiments_in_set']
    enzymes = []
    organisms = []
    total_f_size = 0
    for exp in rep_resp:
        exp_resp = ff_utils.get_metadata(exp, connection=ff)
        report[exp_resp['accession']] = []
        if not organisms:
            biosample = ff_utils.get_metadata(exp_resp['biosample'], connection=ff, frame='embedded')
            organisms = list(set([bs['individual']['organism']['display_title'] for bs in biosample['biosource']]))
            if len(organisms) != 1:
                print('multiple organisms in set', my_rep_set['accession'])
                break
        exp_files = exp_resp['files']
        enzyme = exp_resp.get('digestion_enzyme')
        if enzyme:
            enzymes.append(enzyme)
        for fastq_file in exp_files:
            file_resp = ff_utils.get_metadata(fastq_file, connection=ff)
            if not file_resp.get('file_size'):
                print("WARNING!", file_resp['accession'], 'does not have filesize')
            else:
                total_f_size += file_resp['file_size']
            # skip pair no 2
            if file_resp.get('paired_end') == '2':
                continue
            # exclude miseq
            if exclude_miseq:
                if file_resp.get('instrument') == 'Illumina MiSeq':
                    # print 'skipping miseq files', exp
                    continue
            # Some checks before running
            # check if status is deleted
            if file_resp['status'] == 'deleted':
                print('deleted file', file_resp['accession'], 'in', my_rep_set['accession'])
                continue
            # if no uploaded file in the file item report and skip
            if not file_resp.get('filename'):
                print(file_resp['accession'], "does not have a file")
                continue
            # check if file is in s3
            head_info = tibanna.s3.does_key_exist(file_resp['upload_key'], tibanna.s3.raw_file_bucket)
            if not head_info:
                print(file_resp['accession'], "does not have a file in S3")
                continue
            # check that file has a pair
            f1 = file_resp['@id']
            f2 = ''
            relations = file_resp.get('related_files')
            for relation in relations:
                if relation['relationship_type'] == 'paired with':
                    f2 = relation['file']
            if not f2:
                print(f1, 'does not have a pair')
                continue
            report[exp_resp['accession']].append((f1, f2))

    # get the organism
    if len(list(set(organisms))) == 1:
        organism = organisms[0]
    else:
        organism = None

    # get the enzyme
    if len(list(set(enzymes))) == 1:
        enz = enzymes[0].split('/')[2]
    else:
        enz = None

    bwa = bwa_index.get(organism)
    chrsize = chr_size.get(organism)
    enz_file = re_nz.get(organism).get(enz)

    return report, organism, enz, bwa, chrsize, enz_file, int(total_f_size/(1024*1024*1024))


def get_wfr_out(file_id, wfr_name, file_format, ff, run=100):
    emb_file = ff_utils.get_metadata(file_id, connection=ff, frame='embedded')
    workflows = emb_file.get('workflow_run_inputs')
    wfr = {}
    run_status = 'did not run'

    # add run time to wfr
    if workflows:
        for a_wfr in workflows:
            wfr_time = datetime.strptime(a_wfr['display_title'].split(' run ')[1], '%Y-%m-%d %H:%M:%S.%f')
            a_wfr['run_hours'] = (datetime.utcnow()-wfr_time).total_seconds()/3600
            a_wfr['run_type'] = a_wfr['display_title'].split(' run ')[0]
    # sort wfrs
        workflows = sorted(workflows, key=lambda k: (k['run_type'], -k['run_hours']))
    try:
        last_wfr = [i for i in workflows if i['run_type'] == wfr_name][-1]
    except:
        return "no workflow in file"

    wfr = ff_utils.get_metadata(last_wfr['uuid'], connection=ff)
    run_duration = last_wfr['run_hours']
    run_status = wfr['run_status']

    if run_status == 'complete':
        outputs = wfr.get('output_files')
        if file_format:
            file_id = [i['value'] for i in outputs if i['format'] == file_format][0]
            if file_id:
                return file_id
            else:
                return "no file found"
        # some runs, like qc, don't have a real file output
        else:
            return 'complete'
    elif run_status != 'error' and run_duration < run:
        # print(run_duration)
        return "running"
    else:
        return "no completed run"


def add_processed_files(item_id, list_pc, ff):
    # patch the exp or set
    patch_data = {'processed_files': list_pc}
    ff_utils.patch_metadata(patch_data, obj_id=item_id, connection=ff)
    return


def release_files(set_id, list_items, ff):
    item_status = ff_utils.get_metadata(set_id, connection=ff)['status']
    # bring files to same status as experiments and sets
    if item_status in ['released', 'released to project']:
        for a_file in list_items:
            it_resp = ff_utils.get_metadata(a_file, connection=ff)
            workflow = it_resp.get('workflow_run_outputs')
            # release the wfr that produced the file
            if workflow:
                ff_utils.patch_metadata({"status": item_status}, obj_id=workflow[0], connection=ff)
            ff_utils.patch_metadata({"status": item_status}, obj_id=a_file, connection=ff)


def run_missing_wfr(wf_info, input_files, run_name, ff, env, tibanna):
    all_inputs = []
    for arg, files in input_files.iteritems():
        inp = extract_file_info(files, arg, tibanna, ff)
        all_inputs.append(inp)
    wf_name = wf_info['wf_name']
    wf_uuid = wf_info['wf_uuid']
    parameters = wf_info['parameters']
    input_json = run_json(all_inputs, env, parameters, wf_uuid, wf_name, run_name, tibanna)
    # print input_json
    run_workflow(input_json)
    time.sleep(30)


def extract_nz_file(acc, ff):
    mapping = {"HindIII": "6", "DpnII": "4", "MboI": "4", "NcoI": "6"}
    chr_size = {"human": "4DNFI823LSII",
                "mouse": "4DNFI3UBJ3HZ"}
    exp_resp = ff_utils.get_metadata(acc, connection=ff)
    # get enzyme
    nz = exp_resp.get('digestion_enzyme')
    if nz:
        nz_num = mapping.get(nz.split('/')[2])
    else:
        return (None, None)
    # get organism
    biosample = ff_utils.get_metadata(exp_resp['biosample'], connection=ff, frame='embedded')
    organisms = list(set([bs['individual']['organism']['display_title'] for bs in biosample['biosource']]))
    if len(organisms) == 1:
        chrsize = chr_size.get(organisms[0])
    else:
        return (None, None)
    return nz_num, chrsize
