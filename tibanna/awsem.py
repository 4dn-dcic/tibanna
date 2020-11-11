import re
import copy
from datetime import datetime
from .base import SerializableObject
from .ec2_utils import Config
from .exceptions import MalFormattedPostrunJsonException, MalFormattedRunJsonException
from .vars import AWSEM_TIME_STAMP_FORMAT
from .nnested_array import flatten


class AwsemRunJson(SerializableObject):
    def __init__(self, Job, config):
        self.create_Job(Job)
        self.config = Config(**config)

    def create_Job(self, Job):
        self.Job = AwsemRunJsonJob(**Job)


class AwsemRunJsonJob(SerializableObject):
    def __init__(self, App, Input, Output=None, JOBID='', start_time=None, Log=None):
        self.App = AwsemRunJsonApp(**App)
        self.Input = AwsemRunJsonInput(**Input)
        if not Output:
            Output = {}
        self.create_Output(Output)
        self.start_time = start_time
        self.JOBID = JOBID
        if not Log:
            Log = {}
        self.Log = Log

        # format check
        self.Input.check_input_files_key_compatibility(self.App.language)


    def create_Output(self, Output):
        self.Output = AwsemPostRunJsonOutput(**Output)

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def start_time_as_str(self):
        if not self.start_time:
            return ''
        else:
            return datetime.strptime(self.start_time, AWSEM_TIME_STAMP_FORMAT)


class AwsemRunJsonApp(SerializableObject):
    def __init__(self, App_name=None, App_version=None, language=None,
                 cwl_url=None, main_cwl=None, other_cwl_files=None,
                 wdl_url=None, main_wdl=None, other_wdl_files=None,
                 container_image=None, command=None,
                 snakemake_url=None, main_snakemake=None, other_snakemake_files=None):
        self.App_name = App_name
        self.App_version = App_version
        self.language = language
        self.cwl_url = cwl_url
        self.main_cwl = main_cwl
        self.other_cwl_files = other_cwl_files
        self.wdl_url = wdl_url
        self.main_wdl = main_wdl
        self.other_wdl_files = other_wdl_files
        self.container_image = container_image
        self.command = command
        self.snakemake_url = snakemake_url
        self.main_snakemake = main_snakemake
        self.other_snakemake_files = other_snakemake_files

class AwsemRunJsonInput(SerializableObject):
    def __init__(self, Input_files_data=None, Input_parameters=None, Secondary_files_data=None,
                 # Input_files_reference is for older postrunjson
                 # Env is missing in older postrunjson
                 Input_files_reference=None, Env=None):
        if not Input_files_data:
            Input_files_data = {}
        if not Input_parameters:
            Input_parameters = {}
        if not Secondary_files_data:
            Secondary_files_data = {}
        self.Input_files_data = {k: AwsemRunJsonInputFile(**v) for k, v in Input_files_data.items()}
        self.Secondary_files_data = {k: AwsemRunJsonInputFile(**v) for k, v in Secondary_files_data.items()}
        self.Input_parameters = Input_parameters
        self.Env = Env
        if Input_files_reference:
            self.Input_files_reference = {k: AwsemRunJsonInputFile(**v) for k, v in Input_files_reference.items()}

    def as_dict_as_cwl_input(self, input_dir='', input_mount_dir_prefix=''):
        d = {k: v.as_dict_as_cwl_input(input_dir, input_mount_dir_prefix) for k, v in self.Input_files_data.items()}
        d.update(self.Input_parameters)
        return d

    def as_dict_as_wdl_input(self, input_dir='', input_mount_dir_prefix=''):
        d = {k: v.as_dict_as_wdl_input(input_dir, input_mount_dir_prefix) for k, v in self.Input_files_data.items()}
        d.update(self.Input_parameters)
        return d

    def check_input_files_key_compatibility(self, language):
        for category in ["Input_files_data", "Secondary_files_data"]:
            for inkey in getattr(self, category):
                if inkey.startswith('file://'):
                    if language not in ['shell', 'snakemake']:
                        raise MalFormattedRunJsonException('input file has to be defined with argument name for CWL and WDL')
                    target = inkey.replace('file://', '') 
                    if not target.startswith('/data1/'):
                        raise Exception('input target directory must be in /data1/')
                    if not target.startswith('/data1/' + language) and \
                        not target.startswith('/data1/input') and \
                        not target.startswith('/data1/out'):
                            raise Exception('input target directory must be in /data1/input, /data1/out or /data1/%s' % language)


class AwsemRunJsonInputFile(SerializableObject):
    def __init__(self, path, profile='', rename='', unzip='', mount=False, **kwargs):  # kwargs includes 'dir' and 'class'
        # profile and rename are missing in the old postrunjson
        self.path = path
        self.profile = profile
        self.rename = rename
        self.unzip = unzip
        self.mount = mount
        # handling reserved name key
        self.class_ = kwargs.get('class', None)
        self.dir_ = kwargs.get('dir', None)

        # field compatibility check
        errmsg = "Incompatible input for file %s: %s and mount cannot be used together."
        if self.rename and len(flatten(self.rename))>0 and self.mount:  # the second condition covers e.g. []
            raise MalFormattedRunJsonException(errmsg % (self.path, 'rename'))
        if self.unzip and self.mount:
            raise MalFormattedRunJsonException(errmsg % (self.path, 'unzip'))

    def as_dict(self):
        d = super().as_dict()
        # handling reserved name key
        for rk in ['class', 'dir']:
            rk_alt = rk + '_'
            if rk_alt in d:
                d[rk] = d[rk_alt]
                del(d[rk_alt])
        return d

    def as_dict_as_cwl_input(self, input_dir='', input_mount_dir_prefix=''):
        if self.mount:
            input_dir = input_mount_dir_prefix + self.dir_
        else:
            input_dir = input_dir
        if self.rename:
            if isinstance(self.rename, list):
                path = self.rename[:]
            else:
                path = self.rename
        else:
            path = self.path
        if isinstance(path, list):
            d = []
            for pi in path:
                if isinstance(pi, list):
                    nested = []
                    for ppi in pi:
                        if isinstance(ppi, list):
                            nested.append([file2cwlfile(pppi, input_dir, self.unzip) for pppi in ppi])
                        else:
                            nested.append(file2cwlfile(ppi, input_dir, self.unzip))
                    d.append(nested)
                else:
                    d.append(file2cwlfile(pi, input_dir, self.unzip))
            return d
        else:
            return file2cwlfile(path, input_dir, self.unzip)

    def as_dict_as_wdl_input(self, input_dir='', input_mount_dir_prefix=''):
        if self.mount:
            input_dir = input_mount_dir_prefix + self.dir_
        else:
            input_dir = input_dir
        if self.rename:
            if isinstance(self.rename, list):
                path = list(self.rename)
            else:
                path = self.rename
        else:
            path = self.path
        if isinstance(path, list):
            d = []
            for pi in path:
                if isinstance(pi, list):
                    nested = []
                    for ppi in pi: 
                        if isinstance(ppi, list):
                            nested.append([file2wdlfile(pppi, input_dir, self.unzip) for pppi in ppi])
                        else:
                            nested.append(file2wdlfile(ppi, input_dir, self.unzip))
                    d.append(nested)
                else:
                    d.append(file2wdlfile(pi, input_dir, self.unzip))
            return d
        else:
            return file2wdlfile(path, input_dir, self.unzip)


class AwsemRunJsonOutput(SerializableObject):
    def __init__(self, output_bucket_directory=None, output_target=None,
                 secondary_output_target=None, alt_cond_output_argnames=None):
        self.output_bucket_directory = output_bucket_directory or {}
        self.output_target = output_target or {}
        self.secondary_output_target = secondary_output_target or {}
        self.alt_cond_output_argnames = alt_cond_output_argnames or {}

        for u, v in self.secondary_output_target.items():
            if not isinstance(v, list):
                self.secondary_output_target[u] = [v]

    def alt_output_target(self, argname_list):
        """In case conditional alternative output targets exist, return alternative output target
        where the output target keys are replaced with the alternative names.
        If not, return output_target itself.
        This function does not actually modify output_target.
        It cannot be applied to custom output targets starting with 'file://'
        We don't need to do the same for secondary files because
        conditional alternative names only occur in WDL which does not support secondary files"""

        # first create a list of keys to be replaced
        replace_list = []
        for k in self.output_target:
            if k.startswith('file://'):
                continue
            if k not in argname_list:
                if k in self.alt_cond_output_argnames:
                    key_exists = False  # initialize
                    for k_alt in self.alt_cond_output_argnames[k]:
                        if k_alt in argname_list:
                            key_exists = True
                            replace_list.append((k, k_alt))
                            break
                    if not key_exists:
                        raise Exception("output target key %s doesn't exist in argname list" % k)
                else:
                    raise Exception("output target key %s doesn't exist in argname list" % k)

        # return the alternated output_target
        alt_output_target = copy.deepcopy(self.output_target)
        for k, k_alt in replace_list:
            alt_output_target[k_alt] = alt_output_target[k]
            del alt_output_target[k]
        return alt_output_target


class AwsemPostRunJson(AwsemRunJson):
    def __init__(self, Job, config, commands=None,log=None):
        super().__init__(Job, config)
        if commands:
            self.commands = commands
        if log:
            self.log = log

    def add_commands(self, commands):
        self.commands = commands

    def add_filesystem(self, filesystem):
        self.Job.add_filesystem(filesystem)

    def create_Job(self, Job):
        self.Job = AwsemPostRunJsonJob(**Job)


class AwsemPostRunJsonJob(AwsemRunJsonJob):
    def __init__(self, App, Input, Output, JOBID,
                 start_time, end_time=None, status=None, Log=None,
                 total_input_size=None, total_output_size=None, total_tmp_size=None,
                 # older postrunjsons don't have these fields
                 filesystem='', instance_id='',
                 Metrics=None):
        super().__init__(App, Input, Output, JOBID, start_time, Log)
        self.end_time = end_time
        self.status = status
        self.filesystem = filesystem
        self.instance_id = instance_id
        self.total_input_size = total_input_size
        self.total_output_size = total_output_size
        self.total_tmp_size = total_tmp_size
        self.Metrics = Metrics

    def create_Output(self, Output):
        self.Output = AwsemPostRunJsonOutput(**Output)

    @property
    def end_time_as_str(self):
        try:
            return datetime.strptime(self.end_time, AWSEM_TIME_STAMP_FORMAT)
        except:
            return None

    def add_filesystem(self, filesystem):
        self.filesystem = filesystem


class AwsemPostRunJsonOutput(AwsemRunJsonOutput):
    def __init__(self, output_bucket_directory=None, output_target=None,
                 secondary_output_target=None, alt_cond_output_argnames=None,
                 **kwargs):  # kwargs includes 'Output files'
        """This class has an additional 'Output files' field which
        stores the output from CWL/WDL runs"""
        super().__init__(output_bucket_directory, output_target,
                         secondary_output_target, alt_cond_output_argnames)
        if 'Output files' in kwargs:
            self.add_output_files(kwargs['Output files'])
        else:
            self.Output_files_ = {}

    @property
    def output_files(self):
        return self.Output_files_

    def add_output_files(self, output_files):
        """add or replace output files. output_files is a dictionary with argnames as keys
           and a dict form of AwsemPostRunJsonOutputFile objects as values"""
        self.Output_files_ = {k: AwsemPostRunJsonOutputFile(**v) for k, v in output_files.items()}

    def as_dict(self):
        d = super().as_dict()
        # handling reserved name key
        if 'Output_files_' in d:
            d['Output files'] = d['Output_files_']
            del(d['Output_files_'])
        return d


class AwsemPostRunJsonOutputFile(SerializableObject):
    def __init__(self, path, target=None, basename=None, checksum=None,
                 location=None, md5sum=None, size=None, secondaryFiles=None,
                 **kwargs):  # kwargs includes 'class'
        # both WDL and CWL
        self.path = path
        self.target = target
        # currently CWL-only
        self.basename = basename
        self.checksum = checksum
        self.location = location
        self.md5sum = md5sum
        self.size = size
        if secondaryFiles:
            if isinstance(secondaryFiles, list):
                self.secondaryFiles = [AwsemPostRunJsonOutputFile(**sf) for sf in secondaryFiles]
            else:
                raise MalFormattedPostrunJsonException("secondaryFiles must be a list")
        else:
            self.secondaryFiles = None
        # handling reserved name key
        self.class_ = kwargs.get('class', None)

    def add_target(self, target):
        self.target = target

    def as_dict(self):
        d = super().as_dict()
        # handling reserved name key
        if 'class_' in d:
            d['class'] = d['class_']
            del(d['class_'])
        return d


def file2cwlfile(filename, dirname, unzip):
    if unzip:
        filename = re.match('(.+)\.{0}$'.format(unzip), filename).group(1)
    if dirname.endswith('/'):
        dirname = dirname.rstrip('/')
    return {"class": 'File', "path": dirname + '/' + filename}


def file2wdlfile(filename, dirname, unzip):
    if unzip:
        filename = re.match('(.+)\.{0}$'.format(unzip), filename).group(1)
    if dirname.endswith('/'):
        dirname = dirname.rstrip('/')
    return dirname + '/' + filename
