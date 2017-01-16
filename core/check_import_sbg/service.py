# -*- coding: utf-8 -*-
from core import utils
import boto3
import json

s3 = boto3.resource('s3')
# TODO: I don't want to call the following in test,
# filter out with env var / DEV_ENV
_api = utils.SBGAPI(utils.get_sbg_keys())


# check the status and other details of import
def handler(event, context):
    # get data
    import_ids = event.get('import_ids')
    input_file_args = event.get('input_file_args')
    sbg = utils.create_sbg_workflow(**event.get('workflow'))
    parameter_dict = event.get('parameter_dict')
    workflow_uuid = event.get('workflow_uuid')

    # create Task for workflow run later
    task_input = utils.SBGTaskInput(sbg.app_name,
                                    project=sbg.project_id,
                                    inputs=parameter_dict)

    print(task_input)

    # initalize metadata parameters and input file array
    metadata_parameters, metadata_input = utils.to_sbg_workflow_args(parameter_dict)

    for idx, import_id in enumerate(import_ids):
        if import_id not in sbg.import_id_list:
            raise Exception("Import is not in list of imported ids")

        data = json.dumps({"import_id": import_id})

        res = _api._get("/storage/imports/" + import_id, data)
        if res.json().get('state') != 'COMPLETED':
            raise Exception("file still uploading")
        else:
            results = res.json().get('result')
            sbg_file_name = results.get('name')
            sbg_file_id = results.get('id')
            arg_name = input_file_args[idx].get('workflow_argument_name')
            arg_uuid = input_file_args[idx].get('uuid')
            task_input.add_inputfile(sbg_file_name, sbg_file_id, arg_name)
            sbg.task_input = task_input
            metadata_input.append({'workflow_argument_name': arg_name, 'value': arg_uuid})

        return {'workflow': sbg.as_dict(),
                'workflow_uuid': workflow_uuid,
                'metadata_parameters': metadata_parameters,
                'metadata_input': metadata_input
                }
