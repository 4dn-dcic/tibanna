import boto3
from tibanna.utils import printlog
# import pandas as pd
# from datetime import datetime
# from datetime import timezone
from datetime import timedelta
import matplotlib.pyplot as plt

# instance_id = 'i-0167a6c2d25ce5822'
# filesystem = "/dev/xvdb"
# filesystem = "/dev/nvme1n1"


class TibannaResource(object):
    def __init__(self, instance_id, filesystem, starttime, endtime):
        self.instance_id = instance_id
        self.filesystem = filesystem
        self.client = boto3.client('cloudwatch', region_name='us-east-1')
        # get resource metrics
        nTimeChunks = (endtime - starttime) / timedelta(days=1)
        if round(nTimeChunks) < nTimeChunks:
            nTimeChunks = round(nTimeChunks) + 1
        else:
            nTimeChunks = round(nTimeChunks)
        print("Spliting run time into %s chunks" % str(nTimeChunks))
        self.starttimes = [starttime + timedelta(days=k) for k in range(0, nTimeChunks)]
        self.endtimes = [starttime + timedelta(days=k+1) for k in range(0, nTimeChunks)]
        self.get_metrics(nTimeChunks)

    def get_metrics(self, nTimeChunks=1):
        """calculate max/min metrics across all time chunks.
        AWS allows only 1440 data points at a time
        which corresponds to 24 hours at 1min interval,
        so we have to split them into chunks.
        """
        max_mem_utilization_percent_chunks, max_mem_utilization_percent_chunks_all_pts = [], []
        max_mem_used_MB_chunks, max_mem_used_MB_chunks_all_pts = [], []
        min_mem_available_MB_chunks, min_mem_available_MB_chunks_all_pts = [], []
        max_cpu_utilization_percent_chunks, max_cpu_utilization_percent_chunks_all_pts = [], []
        max_disk_space_utilization_percent_chunks, max_disk_space_utilization_percent_chunks_all_pts = [], []
        max_disk_space_used_GB_chunks, max_disk_space_used_GB_chunks_all_pts = [], []
        for i in range(0, nTimeChunks):
            self.starttime = self.starttimes[i]
            self.endtime = self.endtimes[i]
            # getting all points for the chunck
            max_mem_utilization_percent_all_pts_tmp = self.max_memory_utilization_all_pts()
            max_mem_used_MB_all_pts_tmp = self.max_memory_used_all_pts()
            min_mem_available_MB_all_pts_tmp = self.min_memory_available_all_pts()
            max_cpu_utilization_percent_all_pts_tmp = self.max_cpu_utilization_all_pts()
            max_disk_space_utilization_percent_all_pts_tmp = self.max_disk_space_utilization_all_pts()
            max_disk_space_used_GB_all_pts_tmp = self.max_disk_space_used_all_pts()

            # saving all points for the chunck
            max_mem_utilization_percent_chunks_all_pts.append(max_mem_utilization_percent_all_pts_tmp)
            max_mem_used_MB_chunks_all_pts.append(max_mem_used_MB_all_pts_tmp)
            min_mem_available_MB_chunks_all_pts.append(min_mem_available_MB_all_pts_tmp)
            max_cpu_utilization_percent_chunks_all_pts.append(max_cpu_utilization_percent_all_pts_tmp)
            max_disk_space_utilization_percent_chunks_all_pts.append(max_disk_space_utilization_percent_all_pts_tmp)
            max_disk_space_used_GB_chunks_all_pts.append(max_disk_space_used_GB_all_pts_tmp)

            # saving only the max or min for the chunck
            max_mem_utilization_percent_chunks.append(self.get_max(max_mem_utilization_percent_all_pts_tmp))
            max_mem_used_MB_chunks.append(self.get_max(max_mem_used_MB_all_pts_tmp))
            min_mem_available_MB_chunks.append(self.get_min(min_mem_available_MB_all_pts_tmp))
            max_cpu_utilization_percent_chunks.append(self.get_max(max_cpu_utilization_percent_all_pts_tmp))
            max_disk_space_utilization_percent_chunks.append(self.get_max(max_disk_space_utilization_percent_all_pts_tmp))
            max_disk_space_used_GB_chunks.append(self.get_max(max_disk_space_used_GB_all_pts_tmp))
        self.max_mem_used_MB = self.choose_max(max_mem_used_MB_chunks)
        self.min_mem_available_MB = self.choose_min(min_mem_available_MB_chunks)
        if self.max_mem_used_MB:
            self.total_mem_MB = self.max_mem_used_MB + self.min_mem_available_MB
            self.max_mem_utilization_percent = self.max_mem_used_MB / self.total_mem_MB * 100
        self.max_cpu_utilization_percent = self.choose_max(max_cpu_utilization_percent_chunks)
        self.max_disk_space_utilization_percent = self.choose_max(max_disk_space_utilization_percent_chunks)
        self.max_disk_space_used_GB = self.choose_max(max_disk_space_used_GB_chunks)

        # plots
        self.plot_single(max_mem_used_MB_chunks_all_pts, 'Memory used in Mb')
        self.plot_single(min_mem_available_MB_chunks_all_pts, 'Memory available in Mb')
        self.plot_single(max_disk_space_used_GB_chunks_all_pts, 'Disk space used in Gb')
        self.plot_percent(max_mem_utilization_percent_chunks_all_pts, max_disk_space_utilization_percent_chunks_all_pts, max_cpu_utilization_percent_chunks_all_pts)


    def choose_max(self, x):
        M = -1
        for v in x:
            if v:
                M = max([v, M])
        if M == -1:
            M = ""
        return(M)

    def choose_min(self, x):
        M = 10000000000
        for v in x:
            if v:
                M = min([v, M])
        if M == 10000000000:
            M = ""
        return(M)

    def get_max(self, x):
        return(max(x) if x else '')

    def get_min(self, x):
        return(min(x) if x else '')

    def as_dict(self):
        d = self.__dict__.copy()
        printlog(d)
        del(d['client'])
        del(d['starttimes'])
        del(d['endtimes'])
        del(d['starttime'])
        del(d['endtime'])
        del(d['filesystem'])
        del(d['instance_id'])
        return(d)

    # def as_table(self):
    #    d = self.as_dict()
    #    return(pd.DataFrame(d.items(), columns=['metric', 'value']))

    # functions that returns onnly max or min (backward compatible)
    def max_memory_utilization(self):
        return(self.get_max(self.max_memory_utilization_all_pts()))

    def max_memory_used(self):
        return(self.get_max(self.max_memory_used_all_pts()))

    def min_memory_available(self):
        return(self.get_min(self.min_memory_available_all_pts()))

    def max_cpu_utilization(self):
        return(self.get_max(self.max_cpu_utilization_all_pts()))

    def max_disk_space_utilization(self):
        return(self.get_max(self.max_disk_space_utilization_all_pts()))

    def max_disk_space_used(self):
        return(self.get_max(self.max_disk_space_used_all_pts()))

    # functions that returns all points
    def max_memory_utilization_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='System/Linux',
            MetricName='MemoryUtilization',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Percent'
        )
        return([r['Maximum'] for r in res['Datapoints']])

    def max_memory_used_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='System/Linux',
            MetricName='MemoryUsed',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Megabytes'
        )
        return([r['Maximum'] for r in res['Datapoints']])

    def min_memory_available_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='System/Linux',
            MetricName='MemoryAvailable',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Minimum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Megabytes'
        )
        return([r['Minimum'] for r in res['Datapoints']])

    def max_cpu_utilization_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60*5,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Percent'
        )
        return([r['Maximum'] for r in res['Datapoints']])

    def max_disk_space_utilization_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='System/Linux',
            MetricName='DiskSpaceUtilization',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': self.instance_id},
                {'Name': 'MountPath', 'Value': '/data1'},
                {'Name': 'Filesystem', 'Value': self.filesystem}
            ],
            Period=60,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Percent'
        )
        return([r['Maximum'] for r in res['Datapoints']])

    def max_disk_space_used_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='System/Linux',
            MetricName='DiskSpaceUsed',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': self.instance_id},
                {'Name': 'MountPath', 'Value': '/data1'},
                {'Name': 'Filesystem', 'Value': self.filesystem}
            ],
            Period=60,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Gigabytes'
        )
        return([r['Maximum'] for r in res['Datapoints']])

    # functions to plot
    def plot_single(self, chuncks_all_pts, ylabel):
        plt.ioff() #rendering off

        y = []
        [y.extend(chunck_all_pts) for chunck_all_pts in chuncks_all_pts]
        plt.figure(figsize=(40,20))
        plt.plot(list(range(len(y))), sorted(y), '-o', linewidth=1.5, markersize=1)
        plt.xlabel('Time [min]', fontsize=32, labelpad=35)
        plt.ylabel(ylabel, fontsize=32, labelpad=35)
        plt.xticks(fontsize=27)
        plt.yticks(fontsize=27)
        plt.ylim(ymin=0)

        # saving the plot
        plt.savefig('_'.join(ylabel.split()).lower() + '.png')

        # clearing plt
        plt.clf()

    def plot_percent(self, mem_chuncks_all_pts, disk_chuncks_all_pts, cpu_chuncks_all_pts):
        plt.ioff() #rendering off

        y_mem, y_disk, y_cpu = [], [], []
        [y_mem.extend(chunck_all_pts) for chunck_all_pts in mem_chuncks_all_pts]
        [y_disk.extend(chunck_all_pts) for chunck_all_pts in disk_chuncks_all_pts]
        [y_cpu.extend(chunck_all_pts) for chunck_all_pts in cpu_chuncks_all_pts]

        plt.figure(figsize=(40,20))
        plt.plot(list(range(len(y_mem))), y_mem, '-o', linewidth=1.5, markersize=1, color='blue', label='Memory Utilization')
        plt.plot(list(range(len(y_disk))), y_disk, '-o', linewidth=1.5, markersize=1, color='purple', label='Disk Utilization')
        x_cpu = list(range(len(y_cpu)))
        plt.plot([x*5 for x in x_cpu], y_cpu, '-o', linewidth=1.5, markersize=1, color='green', label='CPU Utilization') #goes by 5

        plt.xlabel('Time [min]', fontsize=32, labelpad=35)
        plt.ylabel('Percentage', fontsize=32, labelpad=35)
        plt.xticks(fontsize=27)
        plt.yticks(fontsize=27)
        plt.ylim(ymin=0)
        #plt.legend(fontsize=20)
        plt.legend(fontsize=25, loc='upper center', bbox_to_anchor=(0.5, 1.10), ncol=3, fancybox=True)

        # saving the plot
        plt.savefig('utilization_mem_disk_cpu.png')

        # clearing plt
        plt.clf()
