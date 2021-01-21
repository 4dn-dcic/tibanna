import json
import yaml
from collections import namedtuple
from tibanna.utils import create_jobid
from tibanna.ec2_utils import UnicornInput
from tibanna.core import API


StepInput = namedtuple('StepInput', ['name', 'source_step', 'name_in_source'])
StepOutput = namedtuple('StepOutput', ['name'])


class Step(object):
    def __init__(self, name, main_file, inputs, outputs, child_files=None):
        self.name = name
        self.main_file = main_file
        self.inputs = [StepInput(**ip) for ip in inputs]
        self.outputs = [StepOutput(**op) for op in outputs]class Step(object):
        self.child_files = child_files


class Workflow(object):
    """class storing workflow structure
    divided into execution units that
    are run together on the same machine.
    """
    cwl = None

    def __init__(self, cwlfile=None):
        if cwlfile:
            self.cwl = self.read_cwl(cwlfile)

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
