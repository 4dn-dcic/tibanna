import datetime


class Top(object):
    """class TopSeries stores the information of a series of top commands

    ::
        echo -n 'Timestamp: '; date +%F-%H:%M:%S
        top -b -n1 [-i] [-c]

    over short intervals to monitor the same set of processes over time. 

    An example input content looks like below, or a series of these.
    The initialization works at any time interval and can be used as a generic
    class, but the class is designed for the output of a regular top commands above
    run at about 1-minute intervals, which is performed by awsf3 on an AWSEM instance
    through cron jobs. (some can be skipped but there should be no more than 1 per minute).
    This top output can be obtained through ``tibanna log -j <job_id> -t`` or through
    API ``API().log(job_id=<job_id>, top=True)``.

    ::

        Timestamp: 2020-12-18-18:55:37
        top - 18:55:37 up 4 days,  2:37,  0 users,  load average: 5.59, 5.28, 5.76
        Tasks:   7 total,   1 running,   6 sleeping,   0 stopped,   0 zombie
        %Cpu(s):  6.6 us,  0.1 sy,  0.0 ni, 93.2 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
        KiB Mem : 12971188+total, 10379019+free, 20613644 used,  5308056 buff/cache
        KiB Swap:        0 total,        0 free,        0 used. 10834606+avail Mem 

          PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND
          712 root      20   0 36.464g 8.223g  19572 S 100.0  6.6 125:55.12 java -Xmx32g -Xms32g -jar juicer_tools.jar addNorm -w 1000 -d -F out.hic
          17919 ubuntu    20   0   40676   3828   3144 R   6.2  0.0   0:00.01 top -b -n1 -c -i -w 10000

    The default timestamp from top output does not contain dates, which can screw up multi-day processes
    which is common for bioinformatics pipelines. So, an extra timestamp is added before each top command.

    To parse top output content, simply create an object. This will create processes attribute,
    which is a raw parsed result organized by time stamps.

    ::

        top = Top(top_output_content)

    To reorganize the contents by commands, run digest. By default, the max number of commands is 16,
    and if there are more than 16 unique commands, they will be collapsed into prefixes.

    ::

        top.digest()

    To write a csv / tsv file organized by both timestamps (rows) and commands (columns),
    use :func: write_to_csv.

    ::

        top.write_to_csv(...)

    """

    # assume this format for timestamp
    timestamp_format = '%Y-%m-%d-%H:%M:%S'

    # These commands are excluded when parsing the top output
    # Currently only 1-, 2- or 3-word prefixes work.
    exclude_list = ['top', 'docker', 'dockerd', '/usr/bin/dockerd', 'cron',
                    'docker-untar', 'containerd', 'goofys-latest', 'cwltool',
                    '/usr/bin/python3 /usr/local/bin/cwltool', 'containerd-shim',
                    '/usr/bin/python3 /bin/unattended-upgrade',
                    '/usr/bin/python3 /usr/local/bin/awsf3',
                    '/usr/bin/python3 /usr/local/bin/aws s3',
                    'java -jar /usr/local/bin/cromwell.jar',
                    'java -jar /usr/local/bin/cromwell-35.jar']

    def __init__(self, contents):
        """initialization parsed top output content and
        creates processes which is a dictionary with timestamps as keys
        and a list of Process class objects as a value.
        It also creates empty attributes timestamps, commands, cpus and mems
        which can be filled through method :func: digest.
        """
        self.processes = dict()
        self.timestamps = []
        self.commands = []
        self.cpus = dict()
        self.mems = dict()
        self.parse_contents(contents)

    def parse_contents(self, contents):
        is_in_table = False
        for line in contents.splitlines():
            if line.startswith('Timestamp:'):
                timestamp = line.split()[1]
                continue
            if line.lstrip().startswith('PID'):
                is_in_table = True
                continue
            if not line or line.isspace():
                is_in_table = False
            if is_in_table:
                if timestamp not in self.processes:
                    self.processes[timestamp] = []
                process = Process(line)
                if not self.should_skip_process(process):
                    self.processes[timestamp].append(Process(line))

    def digest(self, max_n_commands=16, sort_by='alphabetical'):
        """Fills in timestamps, commands, cpus and mems attributes
        from processes attribute.
        :param max_n_commands: When the number of unique commands exceeds
        this value, they are collapsed into unique prefixes.
        :sort_by: alphabetical|cpu|mem The commands are by default sorted
        alphabetically, but optionally can be sorted by total cpus or total
        mem (in reverser order) (e.g. the first command consumed the most cpu)
        """
        # Reinitializat these so that you get the same results if you run it twice
        self.timestamps = []
        self.commands = []
        self.cpus = dict()
        self.mems = dict()
        # First fill in commands from commands in processes (and collapse if needed.)
        self.commands = self.get_collapsed_commands(max_n_commands)
        # Fill in timestamps, cpus and mems from processes, matching collapsed commands.
        self.nTimepoints = len(self.processes)
        timestamp_ind = 0
        for timestamp in sorted(self.processes):
            # sorted timestamps (columns)
            self.timestamps.append(timestamp)
            # commands (rows)
            for process in self.processes[timestamp]:
                # find a matching collapsed command (i.e. command prefix) and use that as command.
                command = Top.convert_command_to_collapsed_command(process.command, self.commands)
                if command not in self.cpus:
                    self.cpus[command] = [0] * self.nTimepoints
                    self.mems[command] = [0] * self.nTimepoints
                self.cpus[command][timestamp_ind] += process.cpu
                self.mems[command][timestamp_ind] += process.mem
            timestamp_ind += 1
        # sort commands according to total cpu
        self.sort_commands(by=sort_by)

    def get_collapsed_commands(self, max_n_commands):
        """If the number of commands exceeds max_n_commands,
        return a collapsed set of commands
        that consists of prefixes of commands so that
        the total number is within max_n_commands.
        First decide the number of words from the beginning of the commands
        to collapse commands that start with the same words, i.e.
        find the maximum number of words that makes the number of unique commands to be
        bounded by max_n_commands.
        If using only the first word is not sufficient, go down to the characters of
        the first word. If that's still not sufficient, collapse all of them into a single
        command ('all_commands')
        After the collapse, commands that are unique to a collapsed prefix are
        extended back to the original command.
        """

        all_commands = set()
        for timestamp in self.processes:
            all_commands.update(set([pr.command for pr in self.processes[timestamp]]))

        if len(all_commands) <= max_n_commands:
            # no need to collapse
            return list(all_commands)

        # decide the number of words from the beginning of the commands
        # to collapse commands starting with the same words
        all_cmd_lengths = [len(cmd.split()) for cmd in all_commands]  # number of words per command
        max_cmd_length = max(all_cmd_lengths)
        min_cmd_length = min(all_cmd_lengths)
        collapsed_len = max_cmd_length - 1
        n_commands = len(all_commands)
        while(n_commands > max_n_commands and collapsed_len > 1):
            reduced_commands = set()
            for cmd in all_commands:
                reduced_commands.add(Top.first_words(cmd, collapsed_len))
            n_commands = len(reduced_commands)
            collapsed_len -= 1

        # went down to the first words but still too many commands - start splitting characters then
        if n_commands > max_n_commands:
            all_cmd_lengths = [len(cmd.split()[0]) for cmd in all_commands]  # number of characters of the first word
            max_cmd_length = max(all_cmd_lengths)
            min_cmd_length = min(all_cmd_lengths)
            collapsed_len = max_cmd_length - 1
            while(n_commands > max_n_commands and collapsed_len > 1):
                reduced_commands = set()
                for cmd in all_commands:
                    reduced_commands.add(Top.first_characters(cmd.split()[0], collapsed_len))
                n_commands = len(reduced_commands)
                collapsed_len -= 1

        if n_commands > max_n_commands:
            return ['all_commands']
        else:
            # extend reduced commands that don't need to be reduced
            for r_cmd in list(reduced_commands):  # wrap in list so that we can remove elements in the loop
                uniq_cmds = [cmd for cmd in all_commands if cmd.startswith(r_cmd)]
                if len(uniq_cmds) == 1:
                    reduced_commands.remove(r_cmd)
                    reduced_commands.add(uniq_cmds[0])
            return reduced_commands

    def write_to_csv(self, csv_file, metric='cpu', delimiter=',', colname_for_timestamps='timepoints',
                     timestamp_start=None, timestamp_end=None, base=0):
        """write metrics as csv file with commands as columns
        :param metric: 'cpu' or 'mem'
        :param delimiter: default ','
        :param colname_for_timestamps: colunm name for the timepoint column (1st column). default 'timepoints'
        :param timestamp_start: start time in the same timestamp format (e.g. 01:23:45),
                                time stamps will be converted to minutes since start time.
                                The report starts with minute 0.
                                Time points with no top records will be filled with 0.
                                If not specified, the first timestamp in the top commands will be used.
        :param timestamp_end: end time in the same timestamp format (e.g. 01:23:45),
                              The reports will be generated only up to the end time.
                              Time points with no top records will be filled with 0.
                              If not specified, the last timestamp in the top commands will be used.
        :param base: default 0. If 0, minutes start with 0, if 1, minutes are 1-based (shifted by 1).
        """
        metric_array = getattr(self, metric + 's')
        if self.timestamps:
            if not timestamp_start:
                timestamp_start = self.timestamps[0]
            if not timestamp_end:
                timestamp_end = self.timestamps[-1]
            timestamps_as_minutes = self.timestamps_as_minutes(timestamp_start)
            last_minute = self.as_minutes(timestamp_end, timestamp_start)
        else:  # default when timestamps is not available (empty object)
            timestamps_as_minutes = range(0, 5)
            last_minute = 5
        with open(csv_file, 'w') as fo:
            # header
            fo.write(delimiter.join([colname_for_timestamps] + [Top.wrap_in_double_quotes(cmd) for cmd in self.commands]))
            fo.write('\n')
            # contents
            # skip timepoints earlier than timestamp_start
            for i in range(0, len(timestamps_as_minutes)):
                if timestamps_as_minutes[i] >= 0:
                    break
            for clock in range(0, last_minute + 1):
                clock_shifted = clock + base
                if i < len(timestamps_as_minutes) and timestamps_as_minutes[i] == clock:
                    fo.write(delimiter.join([str(clock_shifted)] + [str(metric_array[cmd][i]) for cmd in self.commands]))
                    i += 1
                else:
                    fo.write(delimiter.join([str(clock_shifted)] + ['0' for cmd in self.commands]))  # add 0 for timepoints not reported
                fo.write('\n')

    def should_skip_process(self, process):
        """A predicate function to check if the process should be skipped (excluded).
        It returns True if the input process should be skipped.
        e.g. the top command itself is excluded, as well as docker, awsf3, cwltool, etc.
        the list to be excluded is in self.exclude_list.
        It compares either first word or first two or three words only.
        Kernel threads (single-word commands wrapped in bracket (e.g. [perl]) are also excluded.
        """
        first_word = Top.first_words(process.command, 1)
        first_two_words = Top.first_words(process.command, 2)
        first_three_words = Top.first_words(process.command, 3)
        if first_word in self.exclude_list:
            return True
        elif first_two_words in self.exclude_list:
            return True
        elif first_three_words in self.exclude_list:
            return True
        if first_word.startswith('[') and first_word.endswith(']'):
            return True
        return False

    @staticmethod
    def convert_command_to_collapsed_command(cmd, collapsed_commands):
        if collapsed_commands == 'all_commands':  # collapsed to one command
            return 'all_commands'
        elif cmd in collapsed_commands:  # not collapsed
            return cmd
        else:  # collapsed to prefix
            all_prefixes = [_ for _ in collapsed_commands if cmd.startswith(_)]
            longest_prefix = sorted(all_prefixes, key=lambda x: len(x), reverse=True)[0]
            return longest_prefix

    def total_cpu_per_command(self, command):
        return sum([v for v in self.cpus[command]])

    def total_mem_per_command(self, command):
        return sum([v for v in self.mems[command]])

    def sort_commands(self, by='cpu'):
        """sort self.commands by total cpu (default) or mem in reverse order,
           or alphabetically (by='alphabetical')"""
        if by == 'cpu':
            self.commands = sorted(self.commands, key=lambda x: self.total_cpu_per_command(x), reverse=True)
        elif by == 'mem':
            self.commands = sorted(self.commands, key=lambda x: self.total_mem_per_command(x), reverse=True)
        elif by == 'alphabetical':
            self.commands = sorted(self.commands)

    @classmethod
    def as_minutes(cls, timestamp, timestamp_start):
        """timestamp as minutes since timestamp_start.
        :param timestamp: given timestamp in the same format (e.g. 01:23:45)
        :param timestamp_start: start timestamp in the same format (e.g. 01:20:45)
        In the above example, 3 will be the return value.
        """ 
        dt = cls.as_datetime(timestamp)
        dt_start = cls.as_datetime(timestamp_start)
        # negative numbers are not supported by timedelta, so do each case separately
        if dt > dt_start:
            return round((dt - dt_start).seconds / 60)
        else:
            return -round((dt_start - dt).seconds / 60)

    def timestamps_as_minutes(self, timestamp_start):
        """convert self.timestamps to a list of minutes since timestamp_start
        :param timestamp_start: timestamp in the same format (e.g. 01:23:45)
        """
        return [self.as_minutes(t, timestamp_start) for t in self.timestamps]

    @classmethod
    def as_datetime(cls, timestamp):
        return datetime.datetime.strptime(timestamp, cls.timestamp_format)

    @staticmethod
    def wrap_in_double_quotes(string):
        """wrap a given string with double quotes (e.g. haha -> "haha")
        """
        return '\"' + string + '\"'

    @staticmethod
    def first_words(string, n_words):
        """returns first n words of a string
        e.g. first_words('abc def ghi', 2) ==> 'abc def'
        """
        words = string.split()
        return ' '.join(words[0:min(n_words, len(words))])

    @staticmethod
    def first_characters(string, n_letters):
        """returns first n letters of a string
        e.g. first_characters('abc def ghi', 2) ==> 'ab'
        """
        letters = list(string)
        return ''.join(letters[0:min(n_letters, len(letters))])

    def as_dict(self):
        return self.__dict__


class Process(object):             
    def __init__(self, top_line):
        prinfo_as_list = top_line.lstrip().split()
        self.pid = prinfo_as_list[0]
        self.user = prinfo_as_list[1]
        self.cpu = float(prinfo_as_list[8])
        self.mem = float(prinfo_as_list[9])
        self.command = ' '.join(prinfo_as_list[11:])

    def as_dict(self):
        return self.__dict__
