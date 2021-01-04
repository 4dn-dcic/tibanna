import os
from tibanna import top


top_contents = """

Timestamp: 2020-12-18-18:55:37
top - 18:55:37 up 4 days,  3:18,  2 users,  load average: 2.00, 2.00, 2.30
Tasks: 344 total,   1 running, 343 sleeping,   0 stopped,   0 zombie
%Cpu(s):  6.6 us,  0.1 sy,  0.0 ni, 93.2 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
KiB Mem : 12971188+total, 95469344 free, 28933200 used,  5309352 buff/cache
KiB Swap:        0 total,        0 free,        0 used. 10002531+avail Mem 

  PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND
16962 root      20   0 36.456g 0.011t  19372 S  93.8  8.9 125:11.21 java -jar somejar.jar
17086 root      20   0 36.464g 0.016t  19572 S  70.0 13.0 178:59.28 bwa mem
17919 ubuntu    20   0   40676   3828   3144 R   6.2  0.0   0:00.01 top -b -n1 -c -i -w 10000


Timestamp: 2020-12-18-18:56:37
top - 18:56:37 up 4 days,  3:18,  2 users,  load average: 2.00, 2.00, 2.30
Tasks: 344 total,   1 running, 343 sleeping,   0 stopped,   0 zombie
%Cpu(s):  6.6 us,  0.1 sy,  0.0 ni, 93.2 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
KiB Mem : 12971188+total, 95469344 free, 28933200 used,  5309352 buff/cache
KiB Swap:        0 total,        0 free,        0 used. 10002531+avail Mem

  PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND
16962 root      20   0 36.456g 0.011t  19372 S  92.8  9.9 125:11.21 java -jar somejar.jar
17919 ubuntu    20   0   40676   3828   3144 R   5.2  0.0   0:00.01 top -b -n1 -c -i -w 10000
"""


def test_empty_top():
    top1 = top.Top('')
    top1.digest()
    assert top1.processes == {}
    assert top1.timestamps == []

def test_top():
    top1 = top.Top(top_contents)
    print(top1.as_dict())
    assert hasattr(top1, 'processes')

    timestamp1 = '2020-12-18-18:55:37'
    timestamp2 = '2020-12-18-18:56:37'
    assert timestamp1 in top1.processes
    print(top1.processes[timestamp1])
    assert len( top1.processes[timestamp1]) == 2
    top1dict =  top1.processes[timestamp1][0].as_dict()
    print(top1dict)
    assert top1dict['pid'] == '16962'
    assert top1dict['user'] == 'root'
    assert top1dict['cpu'] == 93.8
    assert top1dict['mem'] == 8.9
    assert top1dict['command'] == 'java -jar somejar.jar'
    top2dict =  top1.processes[timestamp1][1].as_dict()
    print(top2dict)
    assert top2dict['pid'] == '17086'
    assert top2dict['user'] == 'root'
    assert top2dict['cpu'] == 70.0
    assert top2dict['mem'] == 13.0
    assert top2dict['command'] == 'bwa mem'

    assert timestamp2 in top1.processes
    assert len( top1.processes[timestamp2]) == 1
    top3dict =  top1.processes[timestamp2][0].as_dict()
    print(top3dict)
    assert top3dict['pid'] == '16962'
    assert top3dict['user'] == 'root'
    assert top3dict['cpu'] == 92.8
    assert top3dict['mem'] == 9.9
    assert top3dict['command'] == 'java -jar somejar.jar'

def test_digest():
    top1 = top.Top(top_contents)
    top1.digest()
    timestamp1 = '2020-12-18-18:55:37'
    timestamp2 = '2020-12-18-18:56:37'
    assert top1.timestamps == [timestamp1, timestamp2]
    assert top1.commands == ['java -jar somejar.jar', 'bwa mem'] 
    assert top1.cpus == {'java -jar somejar.jar': [93.8, 92.8], 'bwa mem': [70.0, 0]}
    assert top1.mems == {'java -jar somejar.jar': [8.9, 9.9], 'bwa mem': [13.0, 0]}
    assert top1.total_cpu_per_command('java -jar somejar.jar') == 93.8 + 92.8
    assert top1.total_cpu_per_command('bwa mem') == 70.0 + 0
    assert top1.total_mem_per_command('java -jar somejar.jar') == 8.9 + 9.9
    assert top1.total_mem_per_command('bwa mem') == 13.0 + 0

    # change process and redigest
    timestamp3 = '2020-12-18-18:57:37'
    top1.processes[timestamp3] = top1.processes[timestamp2].copy()
    del top1.processes[timestamp2]
    top1.digest()

    assert len(top1.processes) == 2
    assert top1.timestamps == [timestamp1, timestamp3]

def test_write_to_csv():
    top1 = top.Top(top_contents)
    top1.digest()
    test_tsv_file = 'some_tsv_file'
    top1.write_to_csv(test_tsv_file, delimiter='\t', base=1)
    with open(test_tsv_file) as f:
        content = f.read()
    lines = content.splitlines()
    assert len(lines) == 3
    assert lines[0] == 'timepoints\t\"java -jar somejar.jar\"\t\"bwa mem\"'
    assert lines[1] == '1\t93.8\t70.0'
    assert lines[2] == '2\t92.8\t0'

    top1.write_to_csv(test_tsv_file, delimiter='\t', metric='mem', colname_for_timestamps='intervals', base=1)
    with open(test_tsv_file) as f:
        content = f.read()
    lines = content.splitlines()
    assert len(lines) == 3
    assert lines[0] == 'intervals\t\"java -jar somejar.jar\"\t\"bwa mem\"'
    assert lines[1] == '1\t8.9\t13.0'
    assert lines[2] == '2\t9.9\t0'

    # change time stamp to 2 minute interval and re-digest
    top1.processes['2020-12-18-18:57:37'] = top1.processes['2020-12-18-18:56:37'].copy()
    del top1.processes['2020-12-18-18:56:37']
    top1.digest()
    print(top1.as_dict())

    top1.write_to_csv(test_tsv_file, delimiter='\t', metric='mem', base=0, timestamp_start='2020-12-18-18:54:37')
    with open(test_tsv_file) as f:
        content = f.read()
    lines = content.splitlines()
    assert len(lines) == 5
    assert lines[0] == 'timepoints\t\"java -jar somejar.jar\"\t\"bwa mem\"'
    assert lines[1] == '0\t0\t0'
    assert lines[2] == '1\t8.9\t13.0'
    assert lines[3] == '2\t0\t0'
    assert lines[4] == '3\t9.9\t0'

    top1.write_to_csv(test_tsv_file, delimiter='\t', metric='mem', base=1, timestamp_start='2020-12-18-18:56:37', timestamp_end='2020-12-18-18:58:37')
    with open(test_tsv_file) as f:
        content = f.read()
    lines = content.splitlines()
    assert len(lines) == 4
    assert lines[0] == 'timepoints\t\"java -jar somejar.jar\"\t\"bwa mem\"'
    assert lines[1] == '1\t0\t0'
    assert lines[2] == '2\t9.9\t0'
    assert lines[3] == '3\t0\t0'

    top1.write_to_csv(test_tsv_file, metric='mem', base=1, timestamp_start='2020-12-18-18:54:37', timestamp_end='2020-12-18-18:56:37')
    with open(test_tsv_file) as f:
        content = f.read()
    lines = content.splitlines()
    assert len(lines) == 4
    assert lines[0] == 'timepoints,\"java -jar somejar.jar\",\"bwa mem\"'
    assert lines[1] == '1,0,0'
    assert lines[2] == '2,8.9,13.0'
    assert lines[3] == '3,0,0'

    top1.write_to_csv(test_tsv_file, metric='mem', base=1, timestamp_start='2020-12-18-18:53:02', timestamp_end='2020-12-18-18:56:22')
    with open(test_tsv_file) as f:
        content = f.read()
    lines = content.splitlines()
    assert len(lines) == 5
    assert lines[0] == 'timepoints,\"java -jar somejar.jar\",\"bwa mem\"'
    assert lines[1] == '1,0,0'  # 18:53:02
    assert lines[2] == '2,0,0'  # 18:54:02
    assert lines[3] == '3,0,0'  # 18:55:02
    assert lines[4] == '4,8.9,13.0'  # 18:56:02 <- 18:55:37 (first entry), 18:56:22 (end time) are rounded to this one.

    os.remove(test_tsv_file)

def test_wrap_in_double_quotes():
    haha = top.Top.wrap_in_double_quotes('haha')
    assert haha == '"haha"'

def test_get_collapsed_commands():
    top1 = top.Top(top_contents)

    # no need to collapse (not too many commands)
    collapsed_commands = top1.get_collapsed_commands(max_n_commands=16)
    assert set(collapsed_commands) == set(['java -jar somejar.jar', 'bwa mem'])

    top1.processes['2020-12-18-18:56:37'][0].command = 'java -jar some_other_jar.jar'
    collapsed_commands = top1.get_collapsed_commands(max_n_commands=16)
    assert set(collapsed_commands) == set(['java -jar somejar.jar', 'bwa mem', 'java -jar some_other_jar.jar'])
    collapsed_commands = top1.get_collapsed_commands(max_n_commands=2)
    assert set(collapsed_commands) == set(['java -jar', 'bwa mem'])

