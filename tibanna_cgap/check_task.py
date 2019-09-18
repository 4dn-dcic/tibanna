# -*- coding: utf-8 -*-
from .cw_utils import TibannaResource
from tibanna.check_task import CheckTask as CheckTask_


def check_task(input_json):
    return CheckTask(input_json).run()


class CheckTask(CheckTask_):
    TibannaResource = TibannaResource
