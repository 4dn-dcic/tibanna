# -*- coding: utf-8 -*-
from core import sbg_utils, utils, ff_utils
import boto3
import json

s3 = boto3.resource('s3')


# check the status and other details of import
def handler(event, context):
    # get data
    input_file_args = event.get('input_file_args')
    parameter_dict = event.get('parameter_dict')

    # used to automatically determine the environment
    tibanna_settings = event.get('_tibanna', {})
    tibanna = utils.Tibanna(**tibanna_settings)
    sbg = sbg_utils.create_sbg_workflow(token=tibanna.sbg_keys, **event.get('workflow'))
    _api = sbg_utils.SBGAPI(tibanna.sbg_keys)

    ff_meta = ff_utils.create_ffmeta(sbg, **event.get('ff_meta'))
    import_ids = sbg.import_id_list
    pf_meta = event.get('pf_meta')

    # create Task for workflow run later
    task_input = sbg_utils.SBGTaskInput(sbg.app_name,
                                        project=sbg.project_id,
                                        inputs=parameter_dict)

    for idx, import_id in enumerate(import_ids):

        data = json.dumps({"import_id": import_id})
        # TODO: Let this be a funciton of SBGWorkflowRun
        # Soo: We already had this function in  SBGWorkflowRun. What happened to it?
        res = _api._get("/storage/imports/" + import_id, data).json()
        if res.get('state') != 'COMPLETED':
            raise Exception("file still uploading")
        else:
            # No idea why, but sometimes it comes back without
            # results as a sub object
            results = res.get('result', res)
            sbg_file_name = results.get('name')
            sbg_file_id = results.get('id')
            arg_name = input_file_args[idx].get('workflow_argument_name')
            # arg_uuid = input_file_args[idx].get('uuid')
            task_input.add_inputfile(sbg_file_name, sbg_file_id, arg_name)
            sbg.task_input = task_input
            # ff_meta.input_files.append({'workflow_argument_name': arg_name, 'value': arg_uuid})
            # Soo: This information was alreadyin ff_meta that was passed into this function.

        # make all the file export meta-data stuff here
        # TODO: fix ff_meta bugs with input / output files
        ff_meta.post(key=tibanna.ff_keys)

    return {'workflow': sbg.as_dict(),
            'ff_meta': ff_meta.as_dict(),
            'pf_meta': pf_meta,
            "_tibanna": tibanna.as_dict(),
            }
