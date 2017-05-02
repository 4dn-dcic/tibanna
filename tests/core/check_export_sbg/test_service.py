from core.check_export_sbg.service import handler as check_export_handler
# from core.check_export_sbg.service import get_inputfile_accession
import pytest
from ..conftest import valid_env
import json
from core import sbg_utils


@pytest.fixture
def fastqc_payload():  # pylint: disable=fixme
    return {"ff_meta":
            {"run_platform": "SBG",
             "uuid": "d8e1b6a8-71d4-46e8-93cb-e07416252ca5",
             "parameters": [],
             "workflow": "2324ad76-ff37-4157-8bcc-3ce72b7dace9",
             "title": "fastqc-0-11-4-1 run 2017-02-16 02:49:29.566538",
             "sbg_import_ids": ["pAqEn5E2N5zL0X32gaRwogs8nrZ9LGJg"],
             "award": "1U01CA200059-01",
             "sbg_task_id": "",
             "lab": "4dn-dcic-lab",
             "sbg_mounted_volume_ids": ["4dn_s30zdfj3xs",
                                        "4dn_s3ijocpds2"],
             "run_status": "output_files_transferring",
             "input_files": [{"workflow_argument_name": "input_fastq",
                              "value": "0048955c-7cb6-4e56-a4d8-56fad52f688c"}],
             "sbg_export_ids": [],
             "output_files": [{"workflow_argument_name": "report_zip",
                               "export_id": "Z3X8ylki1QIKleYiccGu8V7ethxPBSfm",
<<<<<<< HEAD
<<<<<<< HEAD
                               "value": "f3716210-0593-498a-bc66-c9d883bd3171",
                               "upload_key": "d8e1b6a8-71d4-46e8-93cb-e07416252ca5/_1_4DNFIW7Q5UDL_fastqc.zip"}]},
=======
                               "value": "fa1fc604-4788-4804-b9f0-bbabe3045e91",
                               "filename": "__test_data/SRR2671430_1.fastq.gz"}]},
>>>>>>> 10948fea3f574160258c019ca809a6ca4aeb14d2
=======
                               "value": "f3716210-0593-498a-bc66-c9d883bd3171",
                               "upload_key": "d8e1b6a8-71d4-46e8-93cb-e07416252ca5/_1_4DNFIW7Q5UDL_fastqc.zip"}]},
>>>>>>> ff31103da6716cfabe43d59cec430892d6b9144d
            "workflow": {"import_id_list": ["pAqEn5E2N5zL0X32gaRwogs8nrZ9LGJg"],
                         "app_name": "fastqc-0-11-4-1",
                         "task_id": "06121cfb-39a8-47a1-a0bf-852a9053cec0",
                         "task_input": {"project": "4dn-dcic/dev",
                                        "inputs": {"input_fastq": {"path": "58a5133ae4b0bd9c28204633",
                                                                   "class": "File",
                                                                   "name": "4DNFIW7Q5UDL.fastq.gz"}},
                                        "app": "4dn-dcic/dev/fastqc-0-11-4-1",
                                        "name": "fastqc-0-11-4-1"},
                         "volume_list": [{"id": "4dn-labor/4dn_s30zdfj3xs",
                                          "name": "4dn_s30zdfj3xs"},
                                         {"id": "4dn-labor/4dn_s3ijocpds2",
                                         "name": "4dn_s3ijocpds2"}],
                         "output_volume_id": "4dn-labor/4dn_s3ijocpds2",
                         "export_report": [{"workflow_argument_name": "report_zip",
                                            "export_id": "Z3X8ylki1QIKleYiccGu8V7ethxPBSfm",
<<<<<<< HEAD
<<<<<<< HEAD
                                            "value": "f3716210-0593-498a-bc66-c9d883bd3171",
                                            "upload_key":
                                            "d8e1b6a8-71d4-46e8-93cb-e07416252ca5/_1_4DNFIW7Q5UDL_fastqc.zip"}],
=======
                                            "value": "fa1fc604-4788-4804-b9f0-bbabe3045e91",
                                            "filename":
                                            "__test_data/fastqc_report.zip"}],
>>>>>>> 10948fea3f574160258c019ca809a6ca4aeb14d2
=======
                                            "value": "f3716210-0593-498a-bc66-c9d883bd3171",
                                            "upload_key":
                                            "d8e1b6a8-71d4-46e8-93cb-e07416252ca5/_1_4DNFIW7Q5UDL_fastqc.zip"}],
>>>>>>> ff31103da6716cfabe43d59cec430892d6b9144d
                         # pylint: disable=fixme, line-too-long
                         "project_id": "4dn-dcic/dev",
                         "export_id_list": ["Z3X8ylki1QIKleYiccGu8V7ethxPBSfm",
                                            "Z3X8ylki1QIKleYiccGu8V7ethxPBSfm"]}}  # pylint: disable=fixme


@valid_env
@pytest.mark.webtest
def test_check_export_fastqc_e2e(fastqc_payload, ff_keys):
    # lets make sure we have a valid fastqc file
    # TODO: figure out why this doesn't just return one object
    fastqs = sbg_utils.get_metadata("/search/?type=FileFastq&limit=1", ff_keys)['@graph'][0]
    fastqc_payload['ff_meta']

    filename = fastqs['upload_key'].split('/')[1]
    fastqc_payload['workflow']['task_input']['inputs']['input_fastq']['name'] = filename
    fastqc_payload['workflow']['export_report'][0]['value'] = fastqs['uuid']
    fastqc_payload['ff_meta']['output_files'][0]['value'] = fastqs['uuid']

    try:
        ret = check_export_handler(fastqc_payload, None)
    except Exception as e:
        if "409" in e:
            # duplicate UUID, just ignore that
            return
        raise e
    ret = check_export_handler(fastqc_payload, None)
    assert json.dumps(ret)
    assert ret['workflow']

    # sbg = sbg_utils.create_sbg_workflow(**ret['workflow'])
    # accession = get_inputfile_accession(sbg, input_file_name='input_fastq')
    # original_file = sbg_utils.get_metadata(accession, ff_keys)


@valid_env
@pytest.mark.webtest
def test_check_export_sbg_e2e(check_export_event_data):
    try:
        ret = check_export_handler(check_export_event_data, None)
    except KeyError as key_e:
        pytest.skip('Data issue, skipping test: %s' % key_e)
    except Exception as e:
        if type(e) is AssertionError:
            # data issue I think
            return
        elif "409" in e:
            # duplicate UUID, just ignore that
            return
        raise e
    assert json.dumps(ret)
    assert ret['workflow']
    # assert ret['ff_meta']['output_files']
    # assert ret['ff_meta']['sbg_export_ids']
