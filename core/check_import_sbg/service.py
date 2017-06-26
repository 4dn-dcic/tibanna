# -*- coding: utf-8 -*-
from core import sbg_utils, utils, ff_utils
import boto3

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

    ff_meta = ff_utils.create_ffmeta(sbg, **event.get('ff_meta'))
    # import_ids = sbg.import_id_list
    pf_meta = event.get('pf_meta')

    # create Task for workflow run later
    task_name = sbg.app_name
    if tibanna.settings and tibanna.settings.get('run_name'):
        task_name = tibanna.settings.get('run_name')

    task_input = sbg_utils.SBGTaskInput(task_name,
                                        project=sbg.project_id,
                                        app=sbg.project_id + '/' + sbg.app_name,
                                        inputs=parameter_dict)

    for input_file in input_file_args:
        for import_id in input_file.get('import_ids', []):

            # this will handle checking if the import / file is on sbg, otherwise
            # it will throw an error
            res = sbg.check_import(import_id)

            # No idea why, but sometimes it comes back without
            # results as a sub object
            results = res.get('result', res)
            sbg_file_name = results.get('name')
            sbg_file_id = results.get('id')
            arg_name = input_file.get('workflow_argument_name')
            arg_uuids = input_file.get('uuid')
            # we need to know if this is a list so we can build proper task inputs for sbg
            is_list = isinstance(arg_uuids, (list, tuple))
            task_input.add_inputfile(sbg_file_name, sbg_file_id, arg_name, is_list)
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
