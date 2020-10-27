from awsf3.prerun_utils import create_env_def_file
from tibanna.awsem import AwsemRunJson


def test_create_env_def_file():
    envfilename = 'someenvfile'

    runjson_dict = {'Job': {'App': {'cwl_url': 'someurl',
                                    'main_cwl': 'somecwl',
                                    'other_cwl_files': 'othercwl1,othercwl2'},
                            'Input': {'Env': {'SOME_ENV': '1234'}}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'cwl')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export CWL_URL=someurl\n'
                     'export MAIN_CWL=somecwl\n'
                     'export CWL_FILES="othercwl1 othercwl2"\n'
                     'export OUTBUCKET={}\n'
                     'export PUBLIC_POSTRUN_JSON=0\n'
                     'export SOME_ENV=1234\n'
                     'export PRESERVED_ENV_OPTION="--preserve-environment SOME_ENV "\n'
                     'export DOCKER_ENV_OPTION="-e SOME_ENV "\n')

    assert envfile_content == right_content
