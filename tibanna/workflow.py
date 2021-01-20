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
    def steps(self):
        return []

    @staticmethod
    def read_cwl(cwlfile):
        try:
            with open(cwlfile, 'r') as f:
                return json.load(f)
        except:
            with open(cwlfile, 'r') as f:
                return yaml.load(f, Loader=yaml.FullLoader)


def spawn_jobs(input_json, workflow):
    """This function takes an input json (dict) and a workflow (a Workflow object)
    and returns a list of input json with dependencies.
    """
    return [input_json]  # placeholder
