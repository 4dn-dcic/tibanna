import json
import re


class Target(object):
    """Class handling output_target and secondary_output_target"""

    # source_directory = '/data1/out/'

    def __init__(self, output_bucket):
        self.source = ''
        self.bucket = output_bucket
        self.dest = ''
        self.unzip = False

    @property
    def source_name(self):
        return re.sub('^/data1/((shell|out)/)*', '', self.source)
        # return self.source.replace(self.source_directory, '')

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

    def parse_cwl_target(self, target_key, target_value, output_meta):
        """takes a key-value pair from output_target, parses the content.
        output_meta is a dictionary that contains {<argname>: {'path': <outfile_path_on_awsem>}}"""
        self.source = output_meta[target_key].get('path')
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
                self.dest = target_value['object_key']
        elif isinstance(target_value, str):
            if target_value.startswith('s3://'):  # this allows using different output buckets
                output_path = re.sub('^s3://', '', target_value)
                self.bucket = output_path.split('/')[0]
                self.dest = re.sub('^' + self.bucket + '/', '', output_path)
            else:
                self.dest = target_value  # change file name to what's specified in output_target

    def as_dict(self):
        return self.__dict__


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

    def parse_cwl_target(self, target_key, target_value, output_meta):
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


def create_out_meta(language='cwl', execution_metadata=None, md5dict=None):
    """create a dictionary that contains 'path', 'secondaryFiles', 'md5sum' with argnames as keys.
    For snakemake and shell, returns an empty dictionary (execution_metadata not required).
    secondaryFiles is added only if the language is cwl.
    execution_metadata is a dictionary read from wdl/cwl execution log json file.
    md5dict is a dictionary with key=file path, value=md5sum (optional)."""
    if language in ['cwl', 'wdl'] and not execution_metadata:
        raise Exception("execution_metadata is required for cwl/wdl.")
    out_meta = dict()
    if language == 'wdl':
        for argname, outfile in execution_metadata['outputs'].items():
            if outfile:
                out_meta[argname] = {'path': outfile}
    elif language == 'snakemake' or language == 'shell':
        out_meta = {}
    else:
        # read cwl output json file
        out_meta = execution_metadata

    # add md5
    if not md5dict:
        md5dict = {}
    for of, ofv in out_meta.items():
        if ofv['path'] in md5dict:
            ofv['md5sum'] = md5dict[ofv['path']]
        if 'secondaryFiles' in ofv:
            for sf in ofv['secondaryFiles']:
                if sf['path'] in md5dict:
                    sf['md5sum'] = md5dict[sf['path']]

    return out_meta
