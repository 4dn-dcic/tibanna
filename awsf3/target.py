import re
import os
import boto3
import copy
from zipfile import ZipFile
from io import BytesIO
import mimetypes


class Target(object):
    """Class handling output_target and secondary_output_target"""

    # source_directory = '/data1/out/'

    def __init__(self, output_bucket):
        self.source = ''
        self.bucket = output_bucket
        self.dest = ''
        self.unzip = False
        self.s3 = None  # boto3 client

    @property
    def source_name(self):
        return re.sub('^/data1/((shell|out)/)*', '', self.source)
        # return self.source.replace(self.source_directory, '')

    @property
    def is_valid(self):
        if self.source and self.dest and self.bucket:
            return True
        else:
            return False

    def parse_custom_target(self, target_key, target_value):
        """takes a key-value pair from output_target, parses the content.
        This function only handles custom cases where the key starts with file://
        (not valid CWL/WDL targets)"""
        if target_key.startswith('file://'):
            self.source = target_key.replace('file://', '')
            if not target_value:
                raise Exception("output_target missing for target %s" % target_key)
            self.parse_target_value(target_value)

    def parse_cwl_target(self, target_key, target_value, prj_output_files):
        """takes a key-value pair from output_target, parses the content.
        prj_output_files is a dictionary that contains {<argname>: <AwsemPostRunJsonOutputFile object>"""
        self.source = prj_output_files[target_key].path
        if target_value:
            self.parse_target_value(target_value)
        else:
            self.dest = self.source_name  # do not change file name

    def parse_target_value(self, target_value):
        """target value can be a dictionary with following keys: object_key, bucket_name, object_prefix, unzip.
        or it can be a string that refers to the object_key or in the format of s3://<bucket_name>/<object_key>.
        This function changes attributes bucket, dest, unzip."""
        if isinstance(target_value, dict):
            if 'unzip' in target_value and target_value['unzip'] is True:
                if 'object_prefix' not in target_value:
                    raise Exception("object_prefix must be given with unzip=True")
                self.unzip = True
            if 'bucket_name' in target_value:  # this allows using different output buckets
                self.bucket = target_value['bucket_name']
            if 'object_prefix' in target_value:
                if 'object_key' in target_value:
                    raise Exception("Specify either object_key or object_prefix, but not both in output_target")
                if not target_value['object_prefix'].endswith('/'):
                    target_value['object_prefix'] += '/'
                self.dest = target_value['object_prefix']
            if 'object_key' in target_value:
                if target_value['object_key'].endswith('/'):
                    raise Exception("object_key cannot end with '/' - please use object_prefix instead")
                self.dest = target_value['object_key']
        elif isinstance(target_value, str):
            if target_value.startswith('s3://'):  # this allows using different output buckets
                output_path = re.sub('^s3://', '', target_value)
                self.bucket = output_path.split('/')[0]
                self.dest = re.sub('^' + self.bucket + '/', '', output_path)
            else:
                self.dest = target_value  # change file name to what's specified in output_target

    def as_dict(self):
        d = copy.deepcopy(self.__dict__)
        for attr in self.exclude_from_dict:
            del d[attr]
        return d

    @property
    def exclude_from_dict(self):
        return ['s3']

    def unzip_source(self):
        if not self.unzip:
            raise Exception("Unzip error: unzip=True is not set")
        with open(self.source, 'rb') as zf:
            body = zf.read()
        z = ZipFile(BytesIO(body))
        for content_file_name in z.namelist():
            if content_file_name.endswith('/'):  # only copy files
                continue
            yield {'name': content_file_name, 'content': z.open(content_file_name).read()}
        yield None

    def upload_to_s3(self):
        """upload target to s3, source can be either a file or a directory."""
        if not self.is_valid:
            raise Exception('Upload Error: source / dest must be specified first')
        if not self.s3:
            self.s3 = boto3.client('s3')
        err_msg = "failed to upload output file %s to %s. %s"
        if os.path.isdir(self.source):
            print("source " + self.source + " is a directory")
            print("uploading output directory %s to %s in bucket %s" % (self.source, self.dest, self.bucket))
            if self.unzip:
                print("Warning: unzip option is ignored because the source is a directory.")
            source = self.source.rstrip('/')
            for root, dirs, files in os.walk(source):
                for f in files:
                    source_f = os.path.join(root, f)
                    if root == source:
                        dest_f = os.path.join(self.dest, f)
                    else:
                        dest_subdir = re.sub('^' + source + '/', '', root)
                        dest_f = os.path.join(self.dest, dest_subdir, f)
                    print("source_f=" + source_f)
                    print("dest_f=" + dest_f)
                    try:
                        self.s3.upload_file(source_f, self.bucket, dest_f)
                    except Exception as e:
                        raise Exception(err_msg % (source_f, self.bucket + '/' + dest_f, str(e)))
        elif self.unzip:
            # unzip the content files to S3
            try:
                zip_content = self.unzip_source()
            except:
                print("Unzipping failed: source " + self.source + " may not be a zip file")
            print("source " + self.source + " is a zip file. Unzipping..")
            arcfile = next(zip_content)
            while(arcfile):
                # decide on content type
                content_type = mimetypes.guess_type(arcfile['name'])[0]
                if not content_type:
                    content_type = 'binary/octet-stream'
                # upload to S3
                put_object_args = {'Bucket': self.bucket,
                                   'Key': self.dest + arcfile['name'],
                                   'Body': arcfile['content'],
                                   'ContentType': content_type}
                try:
                    print("Putting object %s to %s in bucket %s" % (arcfile['name'], self.dest + arcfile['name'], self.bucket))
                    self.s3.put_object(**put_object_args)
                except Exception as e:
                    raise Exception("failed to put unzipped content %s for file %s. %s" % (arcfile['name'], self.source, str(e)))
                arcfile = next(zip_content)
        else:
            print("source " + self.source + " is an ordinary file.")
            if self.dest.endswith('/'):
                # self.dest is a prefix
                dest = os.path.join(self.dest, self.source_name)
                print("uploading output source %s to %s in bucket %s" % (self.source, dest, self.bucket))
                try:
                    self.s3.upload_file(self.source, self.bucket, dest)
                except Exception as e:
                    raise Exception(err_msg % (self.source, self.bucket + '/' + dest, str(e)))
            else:
                try:
                    print("uploading output source %s to %s in bucket %s" % (self.source, self.dest, self.bucket))
                    self.s3.upload_file(self.source, self.bucket, self.dest)
                except Exception as e:
                    raise Exception(err_msg % (self.source, self.bucket + '/' + self.dest, str(e)))


class SecondaryTarget(Target):
    def is_matched(self, source_path):
        if not self.dest:
            raise Exception("first calculate dest (destination) to check matching.")
        # check the last three letters between dest and source_path
        if self.dest[-3:] == source_path[-3:]:
            return True
        else:
            return False

    def parse_custom_target(self, target_key, target_value):
        raise Exception("Function disabled")

    def parse_cwl_target(self, target_key, target_value, prj_output_files):
        raise Exception("Function disabled")


class SecondaryTargetList(object):
    def __init__(self, output_bucket):
        self.n = 0  # size of the list (i.e. number of secondary targets)
        self.secondary_targets = []  # list of SecondaryTarget objects
        self.bucket = output_bucket

    def parse_target_values(self, target_values):
        self.n = len(target_values)  # size of the list (i.e. number of secondary targets)
        self.secondary_targets = [SecondaryTarget(self.bucket) for i in range(self.n)]
        for st, tv in zip(self.secondary_targets, target_values):
            st.parse_target_value(tv)

    def reorder_by_source(self, source_paths):
        if len(source_paths) < self.n:
            raise Exception("Not enough source_paths for secondary targets " +
                            "(%d vs %d)" % (len(source_paths), self.n))
        n_assigned = 0
        reordered_secondary_targets = []
        for sp in source_paths:
            matched = False
            for st in self.secondary_targets:
                if st.is_matched(sp):
                    st.source = sp
                    reordered_secondary_targets.append(st)
                    n_assigned += 1
                    matched = True
                    break
            if not matched:
                # if no matching target is defined, use the source name
                additional_st = SecondaryTarget(self.bucket)
                additional_st.source = sp
                additional_st.dest = additional_st.source_name
                reordered_secondary_targets.append(additional_st)
                n_assigned += 1
                self.n += 1

        if n_assigned != self.n:
            raise Exception("Error: Not all secondary output targets are being uploaded!" +
                            "{} vs {}".format(n_assigned, self.n))
        self.secondary_targets = reordered_secondary_targets

    def as_dict(self):
        return [st.as_dict() for st in self.secondary_targets]
