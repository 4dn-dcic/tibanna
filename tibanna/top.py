class Top(object):
    """class TopSeries stores the information of a series of top commands

    ::
        top -b -n1 [-i] [-c -w 20000]

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
        if process.command.split()[0] == 'top':
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
