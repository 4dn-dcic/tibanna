import uuid
from core import utils


def parse_fastqc(summary, data):
    """ Return a quality_metric_fastqc metadata dictionary
    given two fastqc output files, summary.txt (summary_filename)
    and fastqc_data.txt (data_filename) """

    qc_key_list_in_data = ['Total Sequences', 'Sequences flagged as poor quality',
                           'Sequence length', '%GC']
    qc_json = {}
    for line in summary.split('\n'):
        a = line.split('\t')
        qc_json.update({a[1]: a[0]})

    for line in data.split('\n'):
        a = line.strip().split('\t')
        if a[0] in qc_key_list_in_data:
            qc_json.update({a[0]: a[1]})

    # overall quality status
    # (do this before uuid, lab & award, so we'll use only quality metric to determind this. (e.g. if all PASS then PASS))
    qc_json = determine_overall_status ( qc_json )

    # add uuid, lab & award
    qc_json.update({"award": "1U01CA200059-01", "lab": "4dn-dcic-lab", "uuid": uuid.uuid4()})

    return(qc_json)


def determine_overall_status (qc_json):
    """Currently PASS no matter what """
    qc_json.update({'overall_quality_status': 'PASS'})
    return(qc_json)


def parse_fastqc_from_s3(key_for_zipped_file):
    file_names = ['summary.txt', 'fastqc_data.txt']
    files = utils.read_s3_zipfile(key_for_zipped_file, file_names)
    parse_fastqc(files['summary.txt'],
                 files['fastqc_data.txt'])
