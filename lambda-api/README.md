The lambda-API is created as follows:

cd /Users/soo/git/tibanna
chalice new-project lambda-api
#virtualenv lambda-api  ## this breaks git
cd lambda-api
# prepare for app.py, requirements.txt and .chalice/config.json
#source bin/activate  ## don't use venv
pip install -r requirements.txt -t . --upgrade
chalice deploy  # deployment requires security credentials.

#tests
http POST $ENDPOINT_URI/run < ../test_json/test_input_requestbody_launch_workflow_run_sbg.json
http POST $ENDPOINT_URI/run < ../test_json/test_input_requestbody_launch_workflow_run_sbg_2.json

Note: the tests work only when the input file import from a previous run using the same input files is removed from SBG.


