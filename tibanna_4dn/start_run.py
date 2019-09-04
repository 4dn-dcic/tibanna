# -*- coding: utf-8 -*-
# import json
import boto3
import json
import random
import copy
from dcicutils import ff_utils
from tibanna.utils import printlog
from tibanna_ffcommon.exceptions import TibannaStartException
from tibanna_ffcommon.portal_utils import (
    TibannaSettings,
    FormatExtensionMap,
    get_extra_file_key,
    create_ffmeta_input_files_from_ff_input_file_list,
    parse_formatstr,
    process_input_file_info,
    output_target_for_input_extra
)
from .pony_utils import (
    PonyInput,
    WorkflowRunMetadata,
    ProcessedFileMetadata,
    WorkflowRunOutputFiles,
    merge_source_experiments,
    FourfrontStarter
)


def start_run(input_json):
    '''
    this is generic function to run awsem workflow
    based on the data passed in

    workflow_uuid : for now, pass this on. Later we can add a code to automatically retrieve this from app_name.
    Note multiple workflow_uuids can be available for an app_name
    (different versions of the same app could have a different uuid)
    '''
    inp = PonyInput(**input_json)

    starter = FourfrontStarter(**input_json)
    if starter.inp.config.log_bucket and starter.inp.jobid:
        s3 = boto3.client('s3')
        s3.put_object(Body=json.dumps(input_json, indent=4).encode('ascii'),
                      Key=inp.jobid + '.input.json',
                      Bucket=inp.config.log_bucket)
    starter.run()
    return(starter.inp.as_dict())
