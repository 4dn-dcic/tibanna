import json
import os
import time
from tibanna.core import API
from tests.tibanna.post_deployment.conftest import (
    REGION1,
    REGION2,
    DEV_SFN_REGION1,
    DEV_SFN_WITH_COSTUPDATER_REGION1,
    DEV_SFN_REGION2,
    DEV_SFN2_REGION2,
    get_test_json,
)


def test_shell():
    os.environ['AWS_DEFAULT_REGION'] = REGION1
    res = API().run_workflow(input_json=get_test_json('shelltest4.json'), sfn=DEV_SFN_REGION1)
    jobid = res['jobid']
    time.sleep(300)
    status = API().check_status(job_id=jobid)
    assert status == 'SUCCEEDED'


def test_shell_costupdater():
    os.environ['AWS_DEFAULT_REGION'] = REGION1
    res = API().run_workflow(input_json=get_test_json('shelltest4.json'), sfn=DEV_SFN_WITH_COSTUPDATER_REGION1)
    jobid = res['jobid']
    time.sleep(300)
    status_unicorn = API().check_status(job_id=jobid)
    status_costupdater = API().check_status(job_id=jobid, sfn_type="costupdater")
    assert status_unicorn == 'SUCCEEDED' and status_costupdater == 'SUCCEEDED'


def test_ecr():
    os.environ['AWS_DEFAULT_REGION'] = REGION1
    res = API().run_workflow(input_json=get_test_json('shelltest-ecr.json'), sfn=DEV_SFN_REGION1)
    jobid = res['jobid']
    time.sleep(300)
    status = API().check_status(job_id=jobid)
    assert status == 'SUCCEEDED'


def test_shell_region2():
    os.environ['AWS_DEFAULT_REGION'] = REGION2
    res = API().run_workflow(input_json=get_test_json('shelltest4.json'), sfn=DEV_SFN_REGION2)
    jobid = res['jobid']
    time.sleep(300)
    status = API().check_status(job_id=jobid)
    assert status == 'SUCCEEDED'


def test_cw_metrics_region2():
    os.environ['AWS_DEFAULT_REGION'] = REGION2
    res = API().run_workflow(input_json=get_test_json('4dn_bwa.runonly.v1.json'), sfn=DEV_SFN2_REGION2)
    jobid = res['jobid']
    time.sleep(60 * 20)
    status = API().check_status(job_id=jobid)
    assert status == 'SUCCEEDED'
    prj = json.loads(API().log(job_id=jobid, postrunjson=True))
    assert prj['metrics']['max_mem_utilization_percent']
    assert prj['metrics']['max_cpu_utilization_percent']
