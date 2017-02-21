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
    input_file_args = event.get('input_file_args')
    parameter_dict = event.get('parameter_dict')
    sbg = utils.create_sbg_workflow(**event.get('workflow'))
    ff_meta = utils.create_ffmeta(sbg, **event.get('ff_meta'))
    import_ids = sbg.import_id_list

    # create Task for workflow run later
    task_input = utils.SBGTaskInput(sbg.app_name,
                                    project=sbg.project_id,
                                    inputs=parameter_dict)

    temp=[]  # Soo
    temp.append(import_ids)  # Soo
    for idx, import_id in enumerate(import_ids):

        temp.append([idx, import_id])  # Soo
        data = json.dumps({"import_id": import_id})
        # TODO: Let this be a funciton of SBGWorkflowRun 
        # Soo: We already had this function in  SBGWorkflowRun. What happened to it?
        res = _api._get("/storage/imports/" + import_id, data).json()
        if res.get('state') != 'COMPLETED':
            temp.append([idx, res.get('state')])  # Soo
            raise Exception("file still uploading")
        else:
            # No idea why, but sometimes it comes back without
            # results as a sub object
            results = res.get('result', res)
            sbg_file_name = results.get('name')
            sbg_file_id = results.get('id')
            arg_name = input_file_args[idx].get('workflow_argument_name')
            arg_uuid = input_file_args[idx].get('uuid')
            task_input.add_inputfile(sbg_file_name, sbg_file_id, arg_name)
            temp.append(task_input.as_dict())  # Soo
            sbg.task_input = task_input
            ff_meta.input_files.append({'workflow_argument_name': arg_name, 'value': arg_uuid})

        # make all the file export meta-data stuff here
        # TODO: fix ff_meta bugs with input / output files
        # ff_meta.post(key=utils.get_access_keys())

    return {'workflow': sbg.as_dict(),
            'ff_meta': ff_meta.as_dict(),
            'temp': temp
            }
