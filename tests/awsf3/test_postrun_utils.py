import os
import pytest
from awsf3.postrun_utils import (
    create_out_meta,
    parse_commands,
    read_logfile_by_line,
    read_md5file
)


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

def test_create_out_meta_cwl():
    md5dict = {'path1': '683153f0051fef9e778ce0866cfd97e9', 'path2': 'c14105f8209836cd3b1cc1b63b906fed'}
    outmeta = create_out_meta('cwl', {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}}, md5dict=md5dict)
    assert outmeta == {'arg1': {'path': 'path1', 'md5sum': md5dict['path1']},
                       'arg2': {'path': 'path2', 'md5sum': md5dict['path2']}}

def test_create_out_meta_cwl_secondary_files():
    md5dict = {'path1': '683153f0051fef9e778ce0866cfd97e9', 'path2': 'c14105f8209836cd3b1cc1b63b906fed'}
    outmeta = create_out_meta('cwl', {'arg1': {'path': 'path1', 'secondaryFiles': [{'path': 'path2'}]}}, md5dict=md5dict)
    assert outmeta == {'arg1': {'path': 'path1', 'md5sum': md5dict['path1'],
                                'secondaryFiles': [{'path': 'path2', 'md5sum': md5dict['path2']}]}}

def test_create_out_meta_cwl_no_md5():
    outmeta = create_out_meta('cwl', {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}})
    assert outmeta == {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}}

def test_create_out_meta_cwl_no_execution_metadata():
    with pytest.raises(Exception) as ex:
        outmeta = create_out_meta('cwl')
    assert 'execution_metadata' in str(ex)

def test_create_out_meta_wdl():
    md5dict = {'path1': '683153f0051fef9e778ce0866cfd97e9', 'path2': 'c14105f8209836cd3b1cc1b63b906fed'}
    outmeta = create_out_meta('wdl', {'outputs': {'arg1': 'path1', 'arg2': 'path2'}}, md5dict=md5dict)
    assert outmeta == {'arg1': {'path': 'path1', 'md5sum': md5dict['path1']},
                       'arg2': {'path': 'path2', 'md5sum': md5dict['path2']}}

def test_create_out_meta_wdl_no_md5():
    outmeta = create_out_meta('wdl', {'outputs': {'arg1': 'path1', 'arg2': 'path2'}})
    assert outmeta == {'arg1': {'path': 'path1'}, 'arg2': {'path': 'path2'}}

def test_create_out_meta_wdl_no_execution_metadata():
    with pytest.raises(Exception) as ex:
        outmeta = create_out_meta('wdl')
    assert 'execution_metadata' in str(ex)

def test_create_out_meta_snakemake():
    outmeta = create_out_meta('snakemake')
    assert outmeta == {}

def test_create_out_meta_shell():
    outmeta = create_out_meta('shell')
    assert outmeta == {}
