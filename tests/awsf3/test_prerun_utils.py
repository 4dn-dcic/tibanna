import os
import pytest
from awsf3.prerun_utils import (
    create_env_def_file,
    create_mount_command_list,
    create_download_command_list,
    create_download_cmd,
    add_download_cmd,
    determine_key_type
)
from tibanna.awsem import AwsemRunJson, AwsemRunJsonInput


def test_create_env_def_file_cwl():
    """testing create_env_def_file with cwl option and an input Env variable"""
    envfilename = 'someenvfile'

    runjson_dict = {'Job': {'App': {'cwl_url': 'someurl',
                                    'main_cwl': 'somecwl',
                                    'other_cwl_files': 'othercwl1,othercwl2'},
                            'Input': {'Env': {'SOME_ENV': '1234'}},
                            'Output': {'output_bucket_directory': 'somebucket'}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'cwl')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export CWL_URL=someurl\n'
                     'export MAIN_CWL=somecwl\n'
                     'export CWL_FILES="othercwl1 othercwl2"\n'
                     'export OUTBUCKET=somebucket\n'
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
                            'Input': {'Env': {}},
                            'Output': {'output_bucket_directory': 'somebucket'}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'wdl')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export WDL_URL=someurl\n'
                     'export MAIN_WDL=somewdl\n'
                     'export WDL_FILES="otherwdl1 otherwdl2"\n'
                     'export OUTBUCKET=somebucket\n'
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
                            'Input': {'Env': {'ENV1': '1234', 'ENV2': '5678'}},
                            'Output': {'output_bucket_directory': 'somebucket'}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'shell')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export COMMAND="com1;com2"\n'
                     'export CONTAINER_IMAGE=someimage\n'
                     'export OUTBUCKET=somebucket\n'
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
                            'Input': {'Env': {'SOME_ENV': '1234'}},
                            'Output': {'output_bucket_directory': 'somebucket'}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'shell')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export COMMAND="echo $SOME_ENV | xargs -i echo {} > somedir/somefile"\n'
                     'export CONTAINER_IMAGE=someimage\n'
                     'export OUTBUCKET=somebucket\n'
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
                            'Input': {'Env': {}},
                            'Output': {'output_bucket_directory': 'somebucket'}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'shell')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export COMMAND="echo \\"haha\\" > somefile; ls -1 [st]*"\n'
                     'export CONTAINER_IMAGE=someimage\n'
                     'export OUTBUCKET=somebucket\n'
                     'export PUBLIC_POSTRUN_JSON=0\n'
                     'export PRESERVED_ENV_OPTION=""\n'
                     'export DOCKER_ENV_OPTION=""\n')

    assert envfile_content == right_content
    os.remove(envfilename)


def test_create_env_def_file_snakemake():
    """testing create_env_def_file with shell option and two input Env variables"""
    envfilename = 'someenvfile'

    runjson_dict = {'Job': {'App': {'command': 'com1;com2',
                                    'container_image': 'someimage',
                                    'snakemake_url': 'someurl',
                                    'main_snakemake': 'somecwl',
                                    'other_snakemake_files': 'othercwl1,othercwl2'},
                            'Input': {},
                            'Output': {'output_bucket_directory': 'somebucket'}},
                    'config': {'log_bucket': 'somebucket'}}
    runjson = AwsemRunJson(**runjson_dict)
    create_env_def_file(envfilename, runjson, 'shell')

    with open(envfilename, 'r') as f:
        envfile_content = f.read()

    right_content = ('export COMMAND="com1;com2"\n'
                     'export CONTAINER_IMAGE=someimage\n'
                     'export OUTBUCKET=somebucket\n'
                     'export PUBLIC_POSTRUN_JSON=0\n'
                     'export PRESERVED_ENV_OPTION=""\n'
                     'export DOCKER_ENV_OPTION=""\n')

    assert envfile_content == right_content
    os.remove(envfilename)


def test_create_mount_command_list():
    mountcommand_filename = 'some_mountcommand_filename'
    rji_dict = {'arg1': {'path': 'somefile', 'dir': 'somebucket', 'mount': True},
                'arg2': {'path': 'somefile2', 'dir': 'somebucket', 'mount': True},
                'arg3': {'path': 'whatever', 'dir': 'do_not_mount_this_bucket', 'mount': False},
                'arg4': {'path': 'somefile3', 'dir': 'somebucket2', 'mount': True}}
    runjson_input = AwsemRunJsonInput(**{'Input_files_data': rji_dict})
    create_mount_command_list(mountcommand_filename, runjson_input)
    
    with open(mountcommand_filename, 'r') as f:
        mcfile_content = f.read()

    right_content = ('mkdir -p /data1/input-mounted-somebucket\n'
                     'goofys-latest -f somebucket /data1/input-mounted-somebucket &\n'
                     'mkdir -p /data1/input-mounted-somebucket2\n'
                     'goofys-latest -f somebucket2 /data1/input-mounted-somebucket2 &\n')

    assert mcfile_content == right_content
    os.remove(mountcommand_filename)


def test_create_download_command_list_args(mocker):
    dl_command_filename = 'some_dlcommand_filename'
    rji_dict = {'arg1': {'path': 'somefile', 'dir': 'somebucket', 'mount': False},
                'arg2': {'path': 'somefile2.gz', 'dir': 'somebucket', 'mount': False, 'unzip': 'gz'},
                'arg3': {'path': 'whatever', 'dir': 'mount_this_bucket', 'mount': True},
                'arg4': {'path': 'somefile3', 'dir': 'somebucket2', 'mount': False}}
    runjson_input = AwsemRunJsonInput(**{'Input_files_data': rji_dict})
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='File')
    create_download_command_list(dl_command_filename, runjson_input)

    with open(dl_command_filename, 'r') as f:
        dcfile_content = f.read()

    right_content = ('aws s3 cp s3://somebucket/somefile /data1/input/somefile; \n'
                     'aws s3 cp s3://somebucket/somefile2.gz /data1/input/somefile2.gz; '
                     'gunzip /data1/input/somefile2.gz\n'
                     'aws s3 cp s3://somebucket2/somefile3 /data1/input/somefile3; \n')

    assert dcfile_content == right_content
    os.remove(dl_command_filename)


def test_create_download_command_list_args_rename(mocker):
    dl_command_filename = 'some_dlcommand_filename'
    rji_dict = {'arg1': {'path': 'somefile', 'dir': 'somebucket', 'mount': False, 'rename': 'renamed_file'},
                'arg2': {'path': 'somefile2.gz', 'dir': 'somebucket', 'mount': False, 'unzip': 'gz'},
                'arg3': {'path': 'whatever', 'dir': 'mount_this_bucket', 'mount': True},
                'arg4': {'path': 'somefile3', 'dir': 'somebucket2', 'mount': False, 'rename': 'renamed_file2'}}
    runjson_input = AwsemRunJsonInput(**{'Input_files_data': rji_dict})
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='File')
    create_download_command_list(dl_command_filename, runjson_input)

    with open(dl_command_filename, 'r') as f:
        dcfile_content = f.read()

    right_content = ('aws s3 cp s3://somebucket/somefile /data1/input/renamed_file; \n'
                     'aws s3 cp s3://somebucket/somefile2.gz /data1/input/somefile2.gz; '
                     'gunzip /data1/input/somefile2.gz\n'
                     'aws s3 cp s3://somebucket2/somefile3 /data1/input/renamed_file2; \n')

    assert dcfile_content == right_content
    os.remove(dl_command_filename)


def test_create_download_command_list_args_array(mocker):
    dl_command_filename = 'some_dlcommand_filename'
    rji_dict = {'arg1': {'path': [['somefilea', 'somefileb'], ['somefilec']], 'dir': 'somebucket', 'mount': False,
                         'rename': [['renameda', 'renamedb'], ['renamedc']]},
                'arg2': {'path': [['anotherfilea', 'anotherfileb'], ['anotherfilec']], 'dir': 'somebucket', 'mount': False,
                         'rename': ''}}
    runjson_input = AwsemRunJsonInput(**{'Input_files_data': rji_dict})
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='File')
    create_download_command_list(dl_command_filename, runjson_input)

    with open(dl_command_filename, 'r') as f:
        dcfile_content = f.read()

    right_content = ('aws s3 cp s3://somebucket/somefilea /data1/input/renameda; \n'
                     'aws s3 cp s3://somebucket/somefileb /data1/input/renamedb; \n'
                     'aws s3 cp s3://somebucket/somefilec /data1/input/renamedc; \n'
                     'aws s3 cp s3://somebucket/anotherfilea /data1/input/anotherfilea; \n'
                     'aws s3 cp s3://somebucket/anotherfileb /data1/input/anotherfileb; \n'
                     'aws s3 cp s3://somebucket/anotherfilec /data1/input/anotherfilec; \n')

    assert dcfile_content == right_content
    os.remove(dl_command_filename)


def test_create_download_command_list_file_uri(mocker):
    dl_command_filename = 'some_dlcommand_filename'
    rji_dict = {'file:///data1/input/file1': {'path': 'somefile', 'dir': 'somebucket', 'mount': False},
                'file:///data1/input/file2.gz': {'path': 'somefile2.gz', 'dir': 'somebucket', 'mount': False, 'unzip': 'gz'},
                'file:///data1/input/haha': {'path': 'whatever', 'dir': 'mount_this_bucket', 'mount': True},
                'file:///data1/input/file3': {'path': 'somefile3', 'dir': 'somebucket2', 'mount': False}}
    runjson_input = AwsemRunJsonInput(**{'Input_files_data': rji_dict})
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='File')
    create_download_command_list(dl_command_filename, runjson_input)

    with open(dl_command_filename, 'r') as f:
        dcfile_content = f.read()

    right_content = ('aws s3 cp s3://somebucket/somefile /data1/input/file1; \n'
                     'aws s3 cp s3://somebucket/somefile2.gz /data1/input/file2.gz; '
                     'gunzip /data1/input/file2.gz\n'
                     'aws s3 cp s3://somebucket2/somefile3 /data1/input/file3; \n')

    assert dcfile_content == right_content
    os.remove(dl_command_filename)


def test_create_download_cmd_unzip_bz2(mocker):
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='File')
    dc_cmd = create_download_cmd('somebucket', 'somefile.bz2', 'sometarget.bz2', '', 'bz2')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somefile.bz2 sometarget.bz2; bzip2 -d sometarget.bz2; '


def test_create_download_cmd_unzip_bz2(mocker):
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='File')
    dc_cmd = create_download_cmd('somebucket', 'somefile.gz', 'sometarget.gz', '', 'gz')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somefile.gz sometarget.gz; gunzip sometarget.gz'


def test_create_download_cmd_nounzip(mocker):
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='File')
    dc_cmd = create_download_cmd('somebucket', 'somefile.gz', 'sometarget.gz', '', '')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somefile.gz sometarget.gz; '


def test_create_download_cmd_nounzip_profile(mocker):
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='File')
    dc_cmd = create_download_cmd('somebucket', 'somefile.gz', 'sometarget.gz', 'user1', '')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somefile.gz sometarget.gz --profile user1; '


def test_create_download_cmd_unzip_bz2_dir(mocker):
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='Folder')
    dc_cmd = create_download_cmd('somebucket', 'somedir', 'sometarget', '', 'bz2')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somedir sometarget; bzip2 -d sometarget.bz2'
    right_cmd = ('aws s3 cp --recursive s3://somebucket/somedir sometarget; '
                 'for f in `find sometarget -type f`; '
                 'do if [[ $f =~ \\.bz2$ ]]; then bzip2 $f; fi; done;')
    assert dc_cmd == right_cmd


def test_create_download_cmd_unzip_bz2_dir(mocker):
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='Folder')
    dc_cmd = create_download_cmd('somebucket', 'somedir', 'sometarget', '', 'gz')
    right_cmd = ('aws s3 cp --recursive s3://somebucket/somedir sometarget; '
                 'for f in `find sometarget -type f`; '
                 'do if [[ $f =~ \\.gz$ ]]; then gunzip $f; fi; done;')
    assert dc_cmd == right_cmd


def test_create_download_cmd_nounzip_dir(mocker):
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='Folder')
    dc_cmd = create_download_cmd('somebucket', 'somedir', 'sometarget', '', '')
    assert dc_cmd == 'aws s3 cp --recursive s3://somebucket/somedir sometarget; '


def test_create_download_cmd_nounzip_profile_dir(mocker):
    mocker.patch('awsf3.prerun_utils.determine_key_type', return_value='Folder')
    dc_cmd = create_download_cmd('somebucket', 'somedir', 'sometarget', 'user1', '')
    assert dc_cmd == 'aws s3 cp --recursive s3://somebucket/somedir sometarget --profile user1; '


