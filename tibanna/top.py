import datetime


class Top(object):
    """class TopSeries stores the information of a series of top commands

    ::
        top -b -n1 [-i] [-c]

    over short intervals to monitor the same set of processes over time. 

    An example input content looks like

    ::

        top - 18:55:37 up 4 days,  2:37,  0 users,  load average: 5.59, 5.28, 5.76
        Tasks:   7 total,   1 running,   6 sleeping,   0 stopped,   0 zombie
        %Cpu(s):  6.6 us,  0.1 sy,  0.0 ni, 93.2 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
        KiB Mem : 12971188+total, 10379019+free, 20613644 used,  5308056 buff/cache
        KiB Swap:        0 total,        0 free,        0 used. 10834606+avail Mem 

          PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND
          712 root      20   0 36.464g 8.223g  19572 S 100.0  6.6 125:55.12 java -Xmx32g -Xms32g -jar juicer_tools.jar addNorm -w 1000 -d -F out.hic
          17919 ubuntu    20   0   40676   3828   3144 R   6.2  0.0   0:00.01 top -b -n1 -c -i -w 10000

    """

    # assume this format for top output
    timestamp_format = '%H:%M:%S'

    # These commands are excluded from top analysis
    exclude_list = ['top', 'docker', 'dockerd', '/usr/bin/dockerd', 'cron', 'containerd', 'goofys-latest', 'cwltool']

    def __init__(self, contents):
        self.processes = dict()
        self.timestamps = []
        self.commands = []
        self.cpus = dict()
        self.mems = dict()
        self.parse_contents(contents)
        self.digest()

    def parse_contents(self, contents):
        is_in_table = False
        for line in contents.splitlines():
            if line.startswith('top'):
                timestamp = line.split()[2]
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

    def should_skip_process(self, process):
        """if the process should be skipped (excluded) return True.
        e.g. the top command itself is excluded."""
        if process.command.split()[0] in self.exclude_list:
            return True
        return False

    def digest(self):
        self.nTimepoints = len(self.processes)
        timestamp_ind = 0
        for timestamp in sorted(self.processes):
            # sorted timestamps (columns)
            self.timestamps.append(timestamp)
            # commands (rows)
            for process in self.processes[timestamp]:
                command = process.command
                if command not in self.commands:
                    self.commands.append(command)
                    self.cpus[command] = [0] * self.nTimepoints
                    self.mems[command] = [0] * self.nTimepoints
                self.cpus[command][timestamp_ind] += process.cpu
                self.mems[command][timestamp_ind] += process.mem
            timestamp_ind += 1
        self.sort_commands()

    def total_cpu_per_command(self, command):
        return sum([v for v in self.cpus[command]])

    def total_mem_per_command(self, command):
        return sum([v for v in self.mems[command]])

    def sort_commands(self, by='cpu'):
        if by == 'cpu':
            self.commands = sorted(self.commands, key=lambda x: self.total_cpu_per_command(x), reverse=True)
        elif by == 'mem':
            self.commands = sorted(self.commands, key=lambda x: self.total_mem_per_command(x), reverse=True)

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
        if not timestamp_start:
            timestamp_start = self.timestamps[0]
        if not timestamp_end:
            timestamp_end = self.timestamps[-1]
        timestamps_as_minutes = self.timestamps_as_minutes(timestamp_start)
        last_minute = self.as_minutes(timestamp_end, timestamp_start)
        with open(csv_file, 'w') as fo:
            # header
            fo.write(delimiter.join([colname_for_timestamps] + [self.wrap_in_double_quotes(cmd) for cmd in self.commands]))
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
            return int((dt - dt_start).seconds / 60)
        else:
            return -int((dt_start - dt).seconds / 60)

    def timestamps_as_minutes(self, timestamp_start):
        """convert self.timestamps to a list of minutes since timestamp_start
        :param timestamp_start: timestamp in the same format (e.g. 01:23:45)
        """
        return [self.as_minutes(t, timestamp_start) for t in self.timestamps]

    @classmethod
    def as_datetime(cls, timestamp):
        return datetime.datetime.strptime(timestamp, cls.timestamp_format)

    @property
    def timestamps_as_datetime(self):
        return [self.as_datetime(ts) for ts in self.timestamps]

    @classmethod
    def wrap_in_double_quotes(cls, string):
        """wrap a given string with double quotes (e.g. haha -> "haha")
        """
        return '\"' + string + '\"'

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
