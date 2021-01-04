import os
import pytest
import json
import boto3
from datetime import datetime
from awsf3.utils import (
    create_env_def_file,
    create_mount_command_list,
    create_download_command_list,
    create_download_cmd,
    add_download_cmd,
    determine_key_type,
    create_output_files_dict,
    read_md5file,
    update_postrun_json_init,
    update_postrun_json_upload_output,
    postrun_json_final,
    upload_postrun_json,
    upload_to_output_target,
    upload_output
)
from awsf3.log import (
    parse_commands,
    read_logfile_by_line
)
from tibanna.awsem import (
    AwsemRunJson,
    AwsemRunJsonInput,
    AwsemPostRunJsonOutput,
    AwsemPostRunJson
)
from tests.awsf3.conftest import upload_test_bucket


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
                            'JOBID': 'somejobid',
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
    mocker.patch('awsf3.utils.determine_key_type', return_value='File')
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
    mocker.patch('awsf3.utils.determine_key_type', return_value='File')
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
    mocker.patch('awsf3.utils.determine_key_type', return_value='File')
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
    mocker.patch('awsf3.utils.determine_key_type', return_value='File')
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
    mocker.patch('awsf3.utils.determine_key_type', return_value='File')
    dc_cmd = create_download_cmd('somebucket', 'somefile.bz2', 'sometarget.bz2', '', 'bz2')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somefile.bz2 sometarget.bz2; bzip2 -d sometarget.bz2; '


def test_create_download_cmd_unzip_bz2(mocker):
    mocker.patch('awsf3.utils.determine_key_type', return_value='File')
    dc_cmd = create_download_cmd('somebucket', 'somefile.gz', 'sometarget.gz', '', 'gz')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somefile.gz sometarget.gz; gunzip sometarget.gz'


def test_create_download_cmd_nounzip(mocker):
    mocker.patch('awsf3.utils.determine_key_type', return_value='File')
    dc_cmd = create_download_cmd('somebucket', 'somefile.gz', 'sometarget.gz', '', '')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somefile.gz sometarget.gz; '


def test_create_download_cmd_nounzip_profile(mocker):
    mocker.patch('awsf3.utils.determine_key_type', return_value='File')
    dc_cmd = create_download_cmd('somebucket', 'somefile.gz', 'sometarget.gz', 'user1', '')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somefile.gz sometarget.gz --profile user1; '


def test_create_download_cmd_unzip_bz2_dir(mocker):
    mocker.patch('awsf3.utils.determine_key_type', return_value='Folder')
    dc_cmd = create_download_cmd('somebucket', 'somedir', 'sometarget', '', 'bz2')
    assert dc_cmd == 'aws s3 cp s3://somebucket/somedir sometarget; bzip2 -d sometarget.bz2'
    right_cmd = ('aws s3 cp --recursive s3://somebucket/somedir sometarget; '
                 'for f in `find sometarget -type f`; '
                 'do if [[ $f =~ \\.bz2$ ]]; then bzip2 $f; fi; done;')
    assert dc_cmd == right_cmd


def test_create_download_cmd_unzip_bz2_dir(mocker):
    mocker.patch('awsf3.utils.determine_key_type', return_value='Folder')
    dc_cmd = create_download_cmd('somebucket', 'somedir', 'sometarget', '', 'gz')
    right_cmd = ('aws s3 cp --recursive s3://somebucket/somedir sometarget; '
                 'for f in `find sometarget -type f`; '
                 'do if [[ $f =~ \\.gz$ ]]; then gunzip $f; fi; done;')
    assert dc_cmd == right_cmd


def test_create_download_cmd_nounzip_dir(mocker):
    mocker.patch('awsf3.utils.determine_key_type', return_value='Folder')
    dc_cmd = create_download_cmd('somebucket', 'somedir', 'sometarget', '', '')
    assert dc_cmd == 'aws s3 cp --recursive s3://somebucket/somedir sometarget; '


def test_create_download_cmd_nounzip_profile_dir(mocker):
    mocker.patch('awsf3.utils.determine_key_type', return_value='Folder')
    dc_cmd = create_download_cmd('somebucket', 'somedir', 'sometarget', 'user1', '')
    assert dc_cmd == 'aws s3 cp --recursive s3://somebucket/somedir sometarget --profile user1; '


def test_read_md5file():
    test_md5file_name = 'some_test_md5_file'
    with open(test_md5file_name, 'w') as fo:
        fo.write('62449071d08c9a9dfa0efbaaa82a62f3\tsomefile\n')  # could be tab-delimited
        fo.write('d41d8cd98f00b204e9800998ecf8427e anotherfile\n')  # could be space-delimited
    md5dict = read_md5file(test_md5file_name)
    assert md5dict == {'somefile': '62449071d08c9a9dfa0efbaaa82a62f3',
                       'anotherfile': 'd41d8cd98f00b204e9800998ecf8427e'}
    os.remove(test_md5file_name)


def test_read_logfile_by_line():
    test_logfile_name = 'some_test_log_file'
    with open(test_logfile_name, 'w') as fo:
        fo.write('1\n2\n3\n')
    log_content = read_logfile_by_line(test_logfile_name)
    assert next(log_content) == '1\n'
    assert next(log_content) == '2\n'
    assert next(log_content) == '3\n'
    assert next(log_content) is None
    os.remove(test_logfile_name)


def test_parse_commands():
    def log_gen():
        log = ['Status: Downloaded newer image',
               '[job clip] /data1/tmpQM7Ol5$ docker \\',
               'run \\',
               '-i \\',
               'duplexa/4dn-repliseq:v13 \\',
               'clip \\',
               'VFL.fastq.gz',
               'Pulled Docker image node:slim',
               'f2b6b4884fc8: Pulling fs layer',
               '[job align] /data1/tmp2EQtm2$ docker \\',
               'run \\',
               '-i \\',
               'duplexa/4dn-repliseq:v14 \\',
               'run-align.sh']

        for line in log:
            yield line
        yield None

    log_content = log_gen()
    commands = parse_commands(log_content)
    assert commands == [['docker', 'run', '-i', 'duplexa/4dn-repliseq:v13', 'clip', 'VFL.fastq.gz'],
                        ['docker', 'run', '-i', 'duplexa/4dn-repliseq:v14', 'run-align.sh']]


def test_create_output_files_dict_cwl():
    md5dict = {'path1': '683153f0051fef9e778ce0866cfd97e9', 'path2': 'c14105f8209836cd3b1cc1b63b906fed'}
    outmeta = create_output_files_dict('cwl', {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}}, md5dict=md5dict)
    assert outmeta == {'arg1': {'path': 'path1', 'md5sum': md5dict['path1']},
                       'arg2': {'path': 'path2', 'md5sum': md5dict['path2']}}


def test_create_output_files_dict_cwl_secondary_files():
    md5dict = {'path1': '683153f0051fef9e778ce0866cfd97e9', 'path2': 'c14105f8209836cd3b1cc1b63b906fed'}
    outmeta = create_output_files_dict('cwl', {'arg1': {'path': 'path1', 'secondaryFiles': [{'path': 'path2'}]}}, md5dict=md5dict)
    assert outmeta == {'arg1': {'path': 'path1', 'md5sum': md5dict['path1'],
                                'secondaryFiles': [{'path': 'path2', 'md5sum': md5dict['path2']}]}}


def test_create_output_files_dict_cwl_no_md5():
    outmeta = create_output_files_dict('cwl', {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}})
    assert outmeta == {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}}


def test_create_output_files_dict_cwl_no_execution_metadata():
    with pytest.raises(Exception) as ex:
        outmeta = create_output_files_dict('cwl')
    assert 'execution_metadata' in str(ex.value)


def test_create_output_files_dict_wdl():
    md5dict = {'path1': '683153f0051fef9e778ce0866cfd97e9', 'path2': 'c14105f8209836cd3b1cc1b63b906fed'}
    outmeta = create_output_files_dict('wdl', {'outputs': {'arg1': 'path1', 'arg2': 'path2'}}, md5dict=md5dict)
    assert outmeta == {'arg1': {'path': 'path1', 'md5sum': md5dict['path1']},
                       'arg2': {'path': 'path2', 'md5sum': md5dict['path2']}}


def test_create_output_files_dict_wdl_no_md5():
    outmeta = create_output_files_dict('wdl', {'outputs': {'arg1': 'path1', 'arg2': 'path2'}})
    assert outmeta == {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}}


def test_create_output_files_dict_wdl_no_execution_metadata():
    with pytest.raises(Exception) as ex:
        outmeta = create_output_files_dict('wdl')
    assert 'execution_metadata' in str(ex.value)


def test_create_output_files_dict_snakemake():
    outmeta = create_output_files_dict('snakemake')
    assert outmeta == {}


def test_create_output_files_dict_shell():
    outmeta = create_output_files_dict('shell')
    assert outmeta == {}


def test_postrun_json_final():
    os.environ['JOB_STATUS'] = '0'
    os.environ['INPUTSIZE'] = '34K'
    os.environ['TEMPSIZE'] = '56M'
    os.environ['OUTPUTSIZE'] = '78K'

    prj = AwsemPostRunJson(**{"Job": {"App": {"App_name": "repliseq-parta"}, "JOBID": "alw3r78v3"}}, strict=False)
    postrun_json_final(prj)
    d_job = prj.Job.as_dict()

    for k in ['end_time', 'status', 'instance_id', 'total_input_size',
              'total_tmp_size', 'total_output_size', 'App', 'JOBID']:
        assert k in d_job

    today = datetime.now().strftime('%Y%m%d')
    assert d_job['end_time'].startswith(today)
    assert len(d_job['end_time'].split('-')) == 3
    assert d_job['status'] == '0'
    assert d_job['total_input_size'] == '34K'
    assert d_job['total_tmp_size'] == '56M'
    assert d_job['total_output_size'] == '78K'


def test_upload_to_output_target():
    """testing comprehensively that includes custom target (file://),
    cwl with two secondary file, wdl with conditional arg names"""
    testfiledir = 'tests/awsf3/test_files/'
    localfile1 = testfiledir + 'some_test_file_to_upload'
    localfile2 = testfiledir + 'some_test_file_to_upload2'
    localfile3 = testfiledir + 'some_test_file_to_upload3.abc'
    localfile4 = testfiledir + 'some_test_file_to_upload3.def'
    localfile5 = testfiledir + 'some_test_file_to_upload3.ghi'

    # prep prjo (postrun_json_output)
    output_target = {'file://' + localfile1: 'somekey',
                     'arg1': 'somekey2',
                     'arg2': 'somekey3.abc'}
    secondary_output_target = {'arg2': ['somekey3.def', 'somekey3.ghi']}
    output_files = {'file://' + localfile1: {'path': localfile1},
                    'arg1b': {'path': localfile2},
                    'arg2': {'path': localfile3,
                             'secondaryFiles': [{'path': localfile4},
                                                {'path': localfile5}]}}
    alt_cond_output_argnames = {'arg1': ['arg1a', 'arg1b']}
    prjo_dict = {'output_target': output_target,
                 'Output files': output_files,
                 'secondary_output_target': secondary_output_target,
                 'alt_cond_output_argnames': alt_cond_output_argnames,
                 'output_bucket_directory': upload_test_bucket}
    prjo = AwsemPostRunJsonOutput(**prjo_dict)

    # run function upload_to_output_target
    upload_to_output_target(prjo)
    
    # still the directory should be uploaded despite the unzip conflict
    s3 = boto3.client('s3')

    def test_and_delete_key(key):
        res = s3.get_object(Bucket=upload_test_bucket, Key=key)
        assert res['Body'].read()
        s3.delete_object(Bucket=upload_test_bucket, Key=key)
        with pytest.raises(Exception) as ex:
            res = s3.get_object(Bucket=upload_test_bucket, Key=key)
        assert 'NoSuchKey' in str(ex.value)

    test_and_delete_key('somekey2')
    test_and_delete_key('somekey3.abc')
    test_and_delete_key('somekey3.def')
    test_and_delete_key('somekey3.ghi')
    test_and_delete_key('somekey')
