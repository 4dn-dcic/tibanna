# -*- coding: utf-8 -*-

from core.utils import powerup
from core.check_task import check_task


def metadata_only(event):
    event.update({'postrunjson': 'metadata_only'})
    return event


@powerup('check_task_awsem', metadata_only)
def handler(event, context):
    return check_task(event)
