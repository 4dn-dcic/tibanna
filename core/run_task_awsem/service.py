# -*- coding: utf-8 -*-

from core.utils import powerup
from core.run_task import run_task


def metadata_only(event):
    event.update({'jobid': 'metadata_only'})
    return event


@powerup('run_task_awsem', metadata_only)
def handler(event, context):
    return run_task(event)
