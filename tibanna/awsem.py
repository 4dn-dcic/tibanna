from .base import SerializableObject
from .ec2_utils import Config
from .exceptions import MalFormattedPostrunJsonException


class AwsemRunJson(SerializableObject):
    def __init__(self, Job, config):
        self.create_Job(Job)
        self.config = Config(**config)

    def create_Job(self, Job):
        self.Job = AwsemRunJsonJob(**Job)


class AwsemRunJsonJob(SerializableObject):
    def __init__(self, App, Input, Output, JOBID, start_time, Log):
        self.App = AwsemRunJsonApp(**App)
        self.Input = AwsemRunJsonInput(**Input)
        self.create_Output(Output)
        self.start_time = start_time
        self.JOBID = JOBID
        self.Log = Log

    def create_Output(self, Output):
        self.Output = AwsemPostRunJsonOutput(**Output)


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


class AwsemRunJsonInput(SerializableObject):
    def __init__(self, Input_files_data, Input_parameters, Secondary_files_data,
                 # Input_files_reference is for older postrunjson
                 # Env is missing in older postrunjson
                 Input_files_reference=None, Env=None):
        self.Input_files_data = {k: AwsemRunJsonInputFile(**v) for k, v in Input_files_data.items()}
        self.Secondary_files_data = {k: AwsemRunJsonInputFile(**v) for k, v in Secondary_files_data.items()}
        self.Input_parameters = Input_parameters
        self.Env = Env
        if Input_files_reference:
            self.Input_files_reference = {k: AwsemRunJsonInputFile(**v) for k, v in Input_files_reference.items()}


class AwsemRunJsonInputFile(SerializableObject):
    def __init__(self, path, profile='', rename='', unzip='', **kwargs):  # kwargs includes 'dir' and 'class'
        # profile and rename are missing in the old postrunjson
        self.path = path
        self.profile = profile
        self.rename = rename
        self.unzip = unzip
        # handling reserved name key
        self.class_ = kwargs.get('class', None)
        self.dir_ = kwargs.get('dir', None)

    def as_dict(self):
        d = super().as_dict()
        # handling reserved name key
        for rk in ['class', 'dir']:
            rk_alt = rk + '_'
            if rk_alt in d:
                d[rk] = d[rk_alt]
                del(d[rk_alt])
        return d


class AwsemRunJsonOutput(SerializableObject):
    def __init__(self, output_bucket_directory=None, output_target=None,
                 secondary_output_target=None, alt_cond_output_argnames=None):
        self.output_bucket_directory = output_bucket_directory
        self.output_target = output_target
        self.secondary_output_target = secondary_output_target
        self.alt_cond_output_argnames = alt_cond_output_argnames


class AwsemPostRunJson(AwsemRunJson):
    def __init__(self, Job, config, commands=None):
        super().__init__(Job, config)
        if commands:
            self.commands = commands

    def create_Job(self, Job):
        self.Job = AwsemPostRunJsonJob(**Job)


class AwsemPostRunJsonJob(AwsemRunJsonJob):
    def __init__(self, App, Input, Output, JOBID,
                 start_time, end_time, status, Log=None,
                 total_input_size=None, total_output_size=None, total_tmp_size=None,
                 # older postrunjsons don't have these fields
                 filesystem=None, instance_id=None,
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


class AwsemPostRunJsonOutput(AwsemRunJsonOutput):
    def __init__(self, output_bucket_directory=None, output_target=None,
                 secondary_output_target=None, alt_cond_output_argnames=None,
                 **kwargs):  # kwargs includes 'Output files'
        """This class has an additional 'Output files' field which
        stores the output from CWL/WDL runs"""
        super().__init__(output_bucket_directory, output_target,
                         secondary_output_target, alt_cond_output_argnames)
        if 'Output files' in kwargs:
            self.Output_files_ = {k: AwsemPostRunJsonOutputFile(**v) for k, v in kwargs['Output files'].items()}

    @property
    def output_files(self):
        return self.Output_files_

    def as_dict(self):
        d = super().as_dict()
        # handling reserved name key
        if 'Output_files_' in d:
            d['Output files'] = d['Output_files_']
            del(d['Output_files_'])
        return d


class AwsemPostRunJsonOutputFile(SerializableObject):
    def __init__(self, path, target, basename=None, checksum=None,
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

    def as_dict(self):
        d = super().as_dict()
        # handling reserved name key
        if 'class_' in d:
            d['class'] = d['class_']
            del(d['class_'])
        return d
