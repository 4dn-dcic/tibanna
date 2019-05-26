import os
from tibanna.vars import Vars as DefaultVars


class Vars(DefaultVars):

    def __init__(self):
        pass

    SECRET = os.environ.get("SECRET", '')
