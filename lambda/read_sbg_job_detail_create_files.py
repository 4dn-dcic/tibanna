#!/usr/bin/python
# We assume that this script is run on EC2 with an IAM role to write to the specified S3 bucket.

import json
import requests
import os
import random

sbg_base_url = "https://api.sbgenomics.com/v2/"
download_url_temp_file = 'download_url_temp_file'

def generate_uuid ():
  rand_uuid_start=''
  for i in xrange(8):
    r=random.choice('abcdef1234567890')
    rand_uuid_start += r
    uuid=rand_uuid_start + "-49e5-4c33-afab-9ec90d65faf3"
  return uuid


def export_file(sbg_job_report, bucket_name, file_metadata_json, workflow_run_metadata_json, token, output_only=True, no_upload=False, no_download=False):

  workflow_run={ 'uuid':generate_uuid(), 'input_files':[], 'output_files':[], 'parameters':[] }

  with open(sbg_job_report,'r') as f:
    report_dict=json.load(f)

  if output_only:
     file_type_list = ['outputs']  ## transfer only output files
  else:
     file_type_list = ['inputs','outputs']  ## transfer both input and output files

  # input/output files
  # download files, upload to s3, add to file metadata json, add to workflow_run dictionary
  for file_type in file_type_list:
    if file_type=='inputs':
       workflow_run_file_type='input_files'
       print 'processing input..'  ## debugging
    else:
       workflow_run_file_type='output_files'
       print 'processing output..'  ## debugging
       
    for k,v in report_dict.get(file_type).iteritems():
      if isinstance(v,dict) and v.get('class')=='File':   ## This is a file
         uuid=process_file(v, bucket_name, file_metadata_json, token, no_upload, no_download)
         workflow_run[workflow_run_file_type].append({'workflow_argument_name':k, 'value':uuid})

      elif isinstance(v,list):
         for v_el in v:
            if isinstance(v_el,dict) and v_el.get('class')=='File':  ## This is a file (v is an array of files)
               uuid=process_file(v_el, bucket_name, file_metadata_json, token, no_upload, no_download)
               workflow_run[workflow_run_file_type].append({'workflow_argument_name':k, 'value':uuid})

  # parameters
  # add to workflow_run dictionary
  # assuming that parameters in the sbg report are either a single value or an array of single values.
  for k,v in report_dict.get('inputs').iteritems():
     if not isinstance(v,dict) and not isinstance(v,list):
        workflow_run['parameters'].append({'workflow_argument_name':k, 'value':v})
     if isinstance(v,list):
        for v_el in v:
           if not isinstance(v_el,dict):
              workflow_run['parameters'].append({'workflow_argument_name':k, 'value':v_el})


  # write to a workflow_run json insert file.
  with open(workflow_run_metadata_json,'w') as fwfrun:
    fwfrun.write( json.dumps(workflow_run,indent=4) )



def process_file(v, bucket_name, file_metadata_json, token, no_upload, no_download):

        sbg_fileID = v['path']
        sbg_filename = v['name']
 
        # download the file to EC2 first
        if not no_download:
           url = sbg_base_url + 'files/' + sbg_fileID + '/download_info'
           headers = {'X-SBG-Auth-Token': token,
                      'Content-Type': 'application/json'}
           resp = requests.get(url, headers=headers)
           download_url = resp.json()['url']
           with open(download_url_temp_file,'w') as fdown:
              fdown.write(download_url)
           os.system('aria2c -i {}'.format(download_url_temp_file))
           os.system('rm -f {}'.format(download_url_temp_file))

        # upload to s3
        if not no_upload:
           os.system("aws s3 cp {} s3://{}".format(sbg_filename,bucket_name))

        # create random accession and uuid
        rand_accession=''
        for i in xrange(8):
          r=random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890')
          rand_accession += r
          accession = "4DNF"+rand_accession

        rand_uuid_start=''
        for i in xrange(8):
          r=random.choice('abcdef1234567890')
          rand_uuid_start += r
          uuid=rand_uuid_start + "-49e5-4c33-afab-9ec90d65faf3"

        # create a meta data file object
        metadata= {
          "accession": accession,
          "filename": 's3://'+bucket_name+'/'+sbg_filename,
          "notes": "sample dcic notes",
          "lab": "4dn-dcic-lab",
          "submitted_by": "admin@admin.com",
          "lab": "4dn-dcic-lab",
          "award": "1U01CA200059-01",
          "file_format": "other",
          #"experiments":["4DNEX067APT1"],
          "uuid": uuid,
          "status": "uploaded"
        }

        # write (append) to a json file
        with open(file_metadata_json,'a') as fmeta:
           json.dump(metadata,fmeta, indent=4)

        return uuid


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="temporary SBG task detail parser")
    parser.add_argument('--sbg_job_report', help='your SBG task detail report')
    parser.add_argument('--bucket_name', help='your 4dn bucket name (including directory)')
    parser.add_argument('--file_metadata_json', help='your output json file to which new file objects will be appended')
    parser.add_argument('--workflow_run_metadata_json', help='your output json file to which a new workflow run object will be written')
    parser.add_argument('--token', help='your 7Bridges api access token')
    parser.add_argument('--output_only', action='store_true', help='export inputs too if false')
    parser.add_argument('--no_upload', action='store_true', help='do not upload but just download and create json')
    parser.add_argument('--no_download', action='store_true', help='do not download but just create json. if this is true, no_upload must be true.')
    args = parser.parse_args()
    export_file(args.sbg_job_report, args.bucket_name, args.file_metadata_json, args.workflow_run_metadata_json, args.token, args.output_only, args.no_upload, args.no_download)


