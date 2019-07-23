import copy
from .exceptions import MalFormattedPostrunJsonException
from .ec2_utils import Config

class AwsemRunJson(object):
    pass


class AwsemPostRunJson(AwsemRunJson):
    def __init__(self, Job, config):
        self.Job = AwsemPostRunJsonJob(Job)
        self.config = Config(config)

    def as_dict(self):
        d = copy.deepcopy(self.__dict__)
        for k in list(d.keys()):
            if d[k] is None:
                del d[k]
        for k, v in d['Job'].items():
                d['Job'][k] = v.as_dict()
        return d 


class AwsemPostRunJsonJob(object):
    def __init__(self, App, Input, Output, Log, JOBID,
                 start_time, end_time, status,
                 filesystem, instance_id,
                 total_input_size, total_output_size, total_tmp_size,
                 Metrics=None):
        self.App = AwsemPostRunJsonApp(**App)
        self.Input = AwsemPostRunJsonInput(**Input)
        self.Output = AwsemPostRunJsonOutput(**Output)
        self.Log = Log
        self.JOBID = JOBID
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.filesystem = filesystem
        self.instance_id = instance_id
        self.total_input_size = total_input_size
        self.total_output_size = total_output_size
        self.total_tmp_size = total_tmp_size
        self.Metrics = Metrics

    def as_dict(self):
        # use deepcopy so that changing this dictionary later won't affect the object
        d = copy.deepcopy(self.__dict__)
        for k in list(d.keys()):
            if d[k] is None:
                del d[k]
        # recursive conversion
        for attr in ['App', 'Input', 'Output']:
            d[attr] = d[attr].as_dict()
        return d


class AwsemPostRunJsonApp(object):
    def __init__(self, App_name, App_version, language,
                 cwl_url=None, main_cwl=None, other_cwl_files=None,
                 wdl_url=None, main_wdl=None, other_wdl_files=None):
        self.App_name = App_name
        self.App_version = App_version
        self.language = language
        self.cwl_url = cwl_url
        self.main_cwl = main_cwl
        self.other_cwl_files = other_cwl_files
        self.wdl_url = wdl_url
        self.main_wdl = main_wdl
        self.other_wdl_files = other_wdl_files

    def as_dict(self):
        # use deepcopy so that changing this dictionary later won't affect the object
        d = copy.deepcopy(self.__dict__)
        for k in list(d.keys()):
            if d[k] is None:
                del d[k]
        return d


class AwsemPostRunJsonInput(object):
    def __init__(self, Input_files_data, Input_parameters, Secondary_files_data, Env):
        self.Input_files_data = {k: AwsemPostRunJsonInputFile(**v) for k, v in Input_files_data.items()}
        self.Secondary_files_data = {k: AwsemPostRunJsonInputFile(**v) for k, v in Secondary_files_data.items()}
        self.Input_parameters = Input_parameters
        self.Env = Env

    def as_dict(self):
        # use deepcopy so that changing this dictionary later won't affect the object
        d = copy.deepcopy(self.__dict__)
        for k in list(d.keys()):
            if d[k] is None:
                del d[k]
        # recursive conversion
        for attr in ['Input_files_data', 'Secondary_files_data']:
            for k, v in d[attr].items():
                d[attr][k] = v.as_dict()
        return d


class AwsemPostRunJsonInputFile(object):
    def __init__(self, path, profile, rename, **kwargs):  # kwargs includes 'dir' and 'class'
        self.path = path
        self.profile = profile
        self.rename = rename
        # handling reserved name key
        self.class_ = kwargs.get('class', None)
        self.dir_ = kwargs.get('dir', None)

    def as_dict(self):
        # use deepcopy so that changing this dictionary later won't affect the object
        d = copy.deepcopy(self.__dict__)
        for k in list(d.keys()):
            if d[k] is None:
                del d[k]
        # handling reserved name key
        for rk in ['class', 'dir']:
            rk_alt = rk + '_'
            if rk_alt in d:
                d[rk] = d[rk_alt]
                del(d[rk_alt])
        return d


class AwsemPostRunJsonOutput(object):
    def __init__(self, output_bucket_directory=None, output_target=None,
                 secondary_output_target=None, alt_cond_output_argnames=None,
                 **kwargs):  # kwargs includes 'Output files'
        self.output_bucket_directory = output_bucket_directory
        self.output_target = output_target
        self.secondary_output_target = secondary_output_target
        self.alt_cond_output_argnames = alt_cond_output_argnames
        if 'Output files' in kwargs:
            self.Output_files_ = {k: AwsemPostRunJsonOutputFile(**v) for k, v in kwargs['Output files'].items()}

    @property        
    def output_files(self):
        return self.Output_files_
   
    def as_dict(self):
        # use deepcopy so that changing this dictionary later won't affect the object
        d = copy.deepcopy(self.__dict__)
        for k in list(d.keys()):
            if d[k] is None:
                del d[k]
        # handling reserved name key
        if 'Output_files_' in d:
            d['Output files'] = d['Output_files_']
            del(d['Output_files_'])
        # recursive conversion
        for k, v in d['Output files'].items():
            d['Output files'][k] = v.as_dict()
        return d


class AwsemPostRunJsonOutputFile(object):
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
        # use deepcopy so that changing this dictionary later won't affect the object
        d = copy.deepcopy(self.__dict__)
        if self.secondaryFiles:
            for i, sf in enumerate(d['secondaryFiles']):
                d['secondaryFiles'][i] = copy.deepcopy(sf.as_dict())
        for k in list(d.keys()):
            if d[k] is None:
                del d[k]
        # handling reserved name key
        if 'class_' in d:
            d['class'] = d['class_']
            del(d['class_'])
        return d

