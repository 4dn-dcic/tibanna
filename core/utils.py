from __future__ import print_function

import json
import boto3
import os
import mimetypes
from zipfile import ZipFile
from io import BytesIO


###########################
# Config
###########################
s3 = boto3.client('s3')
SYS_BUCKET = 'elasticbeanstalk-encoded-4dn-system'
OUTFILE_BUCKET = 'elasticbeanstalk-encoded-4dn-wfoutput-files'
keyfile_name = 'illnevertell'


def get_key(keyfile_name='illnevertell'):
    # Share secret encrypted S3 File
    response = s3.get_object(Bucket=SYS_BUCKET,
                             Key=keyfile_name,
                             SSECustomerKey=os.environ.get("SECRET"),
                             SSECustomerAlgorithm='AES256')
    akey = response['Body'].read()
    try:
        return json.loads(akey)
    except ValueError:
        # maybe its not json after all
        return akey


def read_s3(filename):
    response = s3.get_object(Bucket=OUTFILE_BUCKET,
                             Key=filename)
    return response['Body'].read()


def s3_put(obj, filename):
    '''
    try to guess content type
    '''
    content_type = mimetypes.guess_type(filename)[0]
    if content_type is None:
        content_type = 'binary/octet-stream'
    s3.put_object(Bucket=OUTFILE_BUCKET,
                  Key=filename,
                  Body=obj,
                  ContentType=content_type
                  )


def s3_read_dir(prefix):
    return s3.list_objects(Bucket=OUTFILE_BUCKET,
                           Prefix=prefix)


def s3_delete_dir(prefix):
    # one query get list of all the files we want to delete
    obj_list = s3.list_objects(Bucket=OUTFILE_BUCKET,
                               Prefix=prefix)
    files = obj_list.get('Contents', [])

    # morph file list into format that boto3 wants
    delete_keys = {'Objects': []}
    delete_keys['Objects'] = [{'Key': k} for k in
                              [obj['Key'] for obj in files]]

    # second query deletes all the files, NOTE: Max 1000 files
    if delete_keys['Objects']:
        s3.delete_objects(Bucket=OUTFILE_BUCKET,
                          Delete=delete_keys)


def read_s3_zipfile(s3key, files_to_extract):
    s3_stream = read_s3(s3key)
    bytestream = BytesIO(s3_stream)
    zipstream = ZipFile(bytestream, 'r')
    ret_files = {}

    for name in files_to_extract:
        # search subdirectories for file with name
        # so I don't have to worry about figuring out the subdirs
        zipped_filename = find_file(name, zipstream)
        if zipped_filename:
            ret_files[name] = zipstream.open(zipped_filename).read()
    return ret_files


def unzip_s3_to_s3(zipped_s3key, dest_dir, retfile_names=None):
    if retfile_names is None:
        retfile_names = []

    if not dest_dir.endswith('/'):
        dest_dir += '/'

    s3_stream = read_s3(zipped_s3key)
    # read this badboy to memory, don't go to disk
    bytestream = BytesIO(s3_stream)
    zipstream = ZipFile(bytestream, 'r')

    # directory should be first name in the list
    file_list = zipstream.namelist()
    basedir_name = file_list.pop(0)
    assert basedir_name.endswith('/')

    ret_files = {}
    for file_name in file_list:
        # don't copy dirs just files
        if not file_name.endswith('/'):
            s3_file_name = file_name.replace(basedir_name, dest_dir)
            s3_key = "https://s3.amazonaws.com/%s/%s" % (OUTFILE_BUCKET, s3_file_name)
            # just perf optimization so we don't have to copy
            # files twice that we want to further interogate
            the_file = zipstream.open(file_name, 'r').read()
            file_to_find = file_name.split('/')[-1]
            if file_to_find in retfile_names:
                ret_files[file_to_find] = {'s3key': s3_key,
                                           'data': the_file}
            s3_put(the_file, s3_file_name)

    return ret_files


def find_file(name, zipstream):
    for zipped_filename in zipstream.namelist():
        if zipped_filename.endswith(name):
            return zipped_filename


def current_env():
    return os.environ.get('ENV_NAME', 'test')
