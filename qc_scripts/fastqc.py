import wranglertools.fdnDCIC as fdnDCIC
import json
import zipfile
import re
import random

# this function is redundant - already in lambda app.py
def generate_uuid ():
    rand_uuid_start=''
    rand_uuid_end=''
    for i in xrange(8):
        r=random.choice('abcdef1234567890')
        rand_uuid_start += r
    for i in xrange(12):
        r2=random.choice('abcdef1234567890')
        rand_uuid_end += r2
    uuid=rand_uuid_start + "-49e5-4c33-afab-" + rand_uuid_end
    return uuid


def parse_fastqc ( summary_filename, data_filename ):
    """ Return a quality_metric_fastqc metadata dictionary given two fastqc output files, summary.txt (summary_filename) and fastqc_data.txt (data_filename) """

    qc_key_list_in_data = ['Total Sequences','Sequences flagged as poor quality','Sequence length','%GC']
    
    qc_json={}
    with open(summary_filename, 'r') as f:
        for line in f:
            a = line.split('\t')
            qc_json.update({a[1]: a[0]})
    
    with open(data_filename, 'r') as f:
        for line in f:
            a = line.strip().split('\t')
            if a[0] in qc_key_list_in_data:
                qc_json.update({a[0]: a[1]})
   
    # add uuid, lab & award
    qc_json.update({"award": "1U01CA200059-01", "lab": "4dn-dcic-lab", "uuid": generate_uuid()})

    return(qc_json)



def parse_fastqc_zip ( fastqc_zip_filename, target_dir = '/tmp' ):
    """ Return a quality_metric_fastqc metadata dictionary given a zipped fastqc output file. """
    zip = zipfile.ZipFile( fastqc_zip_filename )
    fastqc_zip_filetitle = re.sub(r'^.+/', '', fastqc_zip_filename)
    target_dir = target_dir + '/' + fastqc_zip_filetitle[:-4]
    zip.extractall( target_dir )
    return ( parse_fastqc( target_dir + '/summary.txt', target_dir + '/fastqc_data.txt' ) )
    


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="file_reference_post")
    parser.add_argument('-s', '--summary_filename', help='summary.txt file')
    parser.add_argument('-d', '--data_filename', help='fastqc_data.txt file')
    parser.add_argument('-z', '--zip_filename', help='fastqc.zip file')
    args = parser.parse_args()

    if args.summary_filename:
        summary_filename = args.summary_filename
    else:
        summary_filename = "/Users/soo/data/hic/fastq/GM12878_SRR1658581_1pc_1_R1_fastqc/summary.txt"

    if args.data_filename:
        data_filename = args.data_filename
    else:
        data_filename = "/Users/soo/data/hic/fastq/GM12878_SRR1658581_1pc_1_R1_fastqc/fastqc_data.txt"

    if args.zip_filename:
        zip_filename = args.zip_filename
    else:
        zip_filename = "/Users/soo/data/hic/fastq/GM12878_SRR1658581_1pc_1_R1_fastqc.zip"

    # print( parse_fastqc( summary_filename, data_filename ) )
    print( json.dumps( parse_fastqc_zip( zip_filename ) ))


