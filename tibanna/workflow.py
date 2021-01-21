import json
import yaml
from tibanna.utils import create_jobid
from tibanna.ec2_utils import UnicornInput
from tibanna.core import API


class Workflow(object):
    """class storing workflow structure
    divided into execution units that
    are run together on the same machine.
    """
    cwl = None

    def __init__(self, cwlfile=None, step_groups=None, auto_group_method='each'):
        """step_groups is a list of groups of step names to run together
        on the same machine. e.g) step_groups=[['bwa'], ['bam_check', 'bam_qc']]
        If not specified, step_groups is defined by default as individual steps
        e.g.) [['bwa'], ['bam_check'], ['bam_qc']]
        """
        if cwlfile:
            self.cwl = self.read_cwl(cwlfile)
        self._step_groups = step_groups
        self.auto_group_method = auto_group_method

    @property
    def step_groups(self):
        if self._step_groups:
            return self._step_groups
        else:
            if self.auto_group_method == 'all':
                return [self.step_names]
            elif self.auto_group_method == 'each':
                return [[_] for _ in self.step_names]

    @property
    def inputs(self):
        return []

    @property
    def outputs(self):
        return []

    @property
    def step_names(self):
        if self.cwl:
            if 'steps' not in self.cwl:
                return []
            if isinstance(self.cwl['steps'], dict):
                return list(self.cwl['steps'].keys())
            elif isinstance(self.cwl['steps'], list):
                return [self.clean_id_in_cwl(_['id']) for _ in self.cwl['steps']]
        return []

    @staticmethod
    def read_cwl(cwlfile):
        try:
            with open(cwlfile, 'r') as f:
                return json.load(f)
        except:
            with open(cwlfile, 'r') as f:
                return yaml.load(f, Loader=yaml.FullLoader)

    @staticmethod
    def clean_id_in_cwl(id):
        return id.lstrip('#')


def spawn_jobs(input_json, workflow):
    """This function takes an input json (dict) and a workflow (a Workflow object)
    and returns a list of input json with dependencies.
    """
    return [input_json]  # placeholder
