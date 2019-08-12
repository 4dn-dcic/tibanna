#!/usr/bin/python
import os
import subprocess
import boto3
import re

def main():
    language = os.environ.get('LANGUAGE')
    if language == 'shell':
        return
    local_wfdir = os.environ.get('LOCAL_WFDIR')
    subprocess.call(['mkdir', '-p', local_wfdir])
    
    if language == 'wdl':
        main_wf = os.environ.get('MAIN_WDL', '')
        wf_files = os.environ.get('WDL_FILES', '')
        wf_url = os.environ.get('WDL_URL')
    elif language == 'snakemake':
        main_wf = os.environ.get('MAIN_SNAKEMAKE', '')
        wf_files = os.environ.get('SNAKEMAKE_FILES', '')
        wf_url = os.environ.get('SNAKEMAKE_URL')
    else:
        main_wf = os.environ.get('MAIN_CWL', '')
        wf_files = os.environ.get('CWL_FILES', '')
        wf_url = os.environ.get('CWL_URL')
    # turn into a list
    if not wf_files:
        wf_files = []
    elif ' ' in wf_files:
        wf_files = wf_files.split(' ')
    else:
        wf_files = [wf_files]
    wf_files.append(main_wf)
    wf_url = wf_url.rstrip('/')
    
    print("main workflow file: %s" % main_wf)
    print("workflow files: " + str(wf_files))
    
    s3 = boto3.client('s3')
    for wf_file in wf_files:
        target = "%s/%s" % (local_wfdir, wf_file)
        source = "%s/%s" % (wf_url, wf_file)
        if wf_url.startswith('http'):
            subprocess.call(["wget", "-O" + target, source])
        elif wf_url.startswith('s3'):
            wf_loc = wf_url.replace('s3://', '')
            bucket_name = wf_loc.split('/')[0]
            if len(wf_loc.split('/')) > 1:
                subdirectory = wf_loc.replace(bucket_name + '/', '')
                key = subdirectory + '/' + wf_file
            else:
                key = wf_file
            print("downloading key %s from bucket %s to target %s" % (key, bucket_name, target))
            if '/' in target:
                targetdir = re.sub('[^/]+$', '', target)
                subprocess.call(["mkdir", "-p", targetdir])
            s3.download_file(Bucket=bucket_name, Key=key, Filename=target)


if __name__ == '__main__':
    main()
