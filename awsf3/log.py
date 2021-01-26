def read_logfile_by_line(logfile):
    """generator function that yields the log file content line by line"""
    with open(logfile, 'r') as f:
        for line in f:
            yield line
    yield None


def parse_commands(log_content):
    """ 
    parse cwl commands from the line-by-line generator of log file content and 
    returns the commands as a list of command line lists, each corresponding to a step run.
    """ 
    command_list = []
    command = []
    in_command = False
    line = next(log_content)
    while(line):
        line = line.strip('\n')
        if '[job' in line and line.endswith('docker \\'):
            line = 'docker \\'  # remove the other stuff
            in_command = True
        if in_command:
            command.append(line.strip('\\').rstrip(' ')) 
            if not line.endswith('\\'):
                in_command = False
                command_list.append(command)
                command = []
        line = next(log_content)
    return(command_list)
