import os
from awsf3.prerun_utils import create_env_def_file
from tibanna.awsem import AwsemRunJson


def test_create_env_def_file_cwl():
    """testing create_env_def_file with cwl option and an input Env variable"""
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
    os.remove(envfilename)


def test_create_env_def_file_wdl():
    """testing create_env_def_file with wdl option and no input Env variable"""
    envfilename = 'someenvfile'

    runjson_dict = {'Job': {'App': {'wdl_url': 'someurl',
                                    'main_wdl': 'somewdl',
                                    'other_wdl_files': 'otherwdl1,otherwdl2'},
                            'Input': {'Env': {}}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'wdl')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export WDL_URL=someurl\n'
                     'export MAIN_WDL=somewdl\n'
                     'export WDL_FILES="otherwdl1 otherwdl2"\n'
                     'export OUTBUCKET={}\n'
                     'export PUBLIC_POSTRUN_JSON=0\n'
                     'export PRESERVED_ENV_OPTION=""\n'
                     'export DOCKER_ENV_OPTION=""\n')

    assert envfile_content == right_content
    os.remove(envfilename)


def test_create_env_def_file_shell():
    """testing create_env_def_file with shell option and two input Env variables"""
    envfilename = 'someenvfile'

    runjson_dict = {'Job': {'App': {'command': 'com1;com2',
                                    'container_image': 'someimage'},
                            'Input': {'Env': {'ENV1': '1234', 'ENV2': '5678'}}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'shell')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export COMMAND="com1;com2"\n'
                     'export CONTAINER_IMAGE=someimage\n'
                     'export OUTBUCKET={}\n'
                     'export PUBLIC_POSTRUN_JSON=0\n'
                     'export ENV1=1234\n'
                     'export ENV2=5678\n'
                     'export PRESERVED_ENV_OPTION="--preserve-environment ENV1 --preserve-environment ENV2 "\n'
                     'export DOCKER_ENV_OPTION="-e ENV1 -e ENV2 "\n')

    assert envfile_content == right_content
    os.remove(envfilename)


def test_create_env_def_file_shell2():
    """testing create_env_def_file with shell option with complex commands and an env variable"""
    envfilename = 'someenvfile'

    complex_command = 'echo $SOME_ENV | xargs -i echo {} > somedir/somefile'
    runjson_dict = {'Job': {'App': {'command': complex_command,
                                    'container_image': 'someimage'},
                            'Input': {'Env': {'SOME_ENV': '1234'}}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'shell')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export COMMAND="echo $SOME_ENV | xargs -i echo {} > somedir/somefile"\n'
                     'export CONTAINER_IMAGE=someimage\n'
                     'export OUTBUCKET={}\n'
                     'export PUBLIC_POSTRUN_JSON=0\n'
                     'export SOME_ENV=1234\n'
                     'export PRESERVED_ENV_OPTION="--preserve-environment SOME_ENV "\n'
                     'export DOCKER_ENV_OPTION="-e SOME_ENV "\n')

    assert envfile_content == right_content
    os.remove(envfilename)


def test_create_env_def_file_shell3():
    """testing create_env_def_file with shell option with complex commands and an env variable.
    double-quotes are escaped when written to the env file ('"' -> '\"')"""
    envfilename = 'someenvfile'

    complex_command = 'echo "haha" > somefile; ls -1 [st]*'
    runjson_dict = {'Job': {'App': {'command': complex_command,
                                    'container_image': 'someimage'},
                            'Input': {'Env': {}}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'shell')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export COMMAND="echo \\"haha\\" > somefile; ls -1 [st]*"\n'
                     'export CONTAINER_IMAGE=someimage\n'
                     'export OUTBUCKET={}\n'
                     'export PUBLIC_POSTRUN_JSON=0\n'
                     'export PRESERVED_ENV_OPTION=""\n'
                     'export DOCKER_ENV_OPTION=""\n')

    assert envfile_content == right_content
    os.remove(envfilename)
