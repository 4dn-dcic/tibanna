# -*- coding: utf-8 -*-

from tibanna.utils import powerup
from tibanna.run_task import run_task


def metadata_only(event):
    event.update({'jobid': 'metadata_only'})
    return event


@powerup('run_task_awsem', metadata_only)
def handler(event, context):
    return run_task(event)
