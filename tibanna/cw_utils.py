import boto3
from tibanna.utils import printlog
# import pandas as pd
# from datetime import datetime
# from datetime import timezone
from datetime import timedelta

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
        max_mem_used_MB_chunks = []
        min_mem_available_MB_chunks = []
        max_cpu_utilization_percent_chunks = []
        max_disk_space_utilization_percent_chunks = []
        max_disk_space_used_GB_chunks = []
        for i in range(0, nTimeChunks):
            self.starttime = self.starttimes[i]
            self.endtime = self.endtimes[i]
            max_mem_used_MB_chunks.append(self.max_memory_used())
            min_mem_available_MB_chunks.append(self.min_memory_available())
            max_cpu_utilization_percent_chunks.append(self.max_cpu_utilization())
            max_disk_space_utilization_percent_chunks.append(self.max_disk_space_utilization())
            max_disk_space_used_GB_chunks.append(self.max_disk_space_used())
        self.max_mem_used_MB = self.choose_max(max_mem_used_MB_chunks)
        self.min_mem_available_MB = self.choose_min(min_mem_available_MB_chunks)
        if self.max_mem_used_MB:
            self.total_mem_MB = self.max_mem_used_MB + self.min_mem_available_MB
            self.max_mem_utilization_percent = self.max_mem_used_MB / self.total_mem_MB * 100
        self.max_cpu_utilization_percent = self.choose_max(max_cpu_utilization_percent_chunks)
        self.max_disk_space_utilization_percent = self.choose_max(max_disk_space_utilization_percent_chunks)
        self.max_disk_space_used_GB = self.choose_max(max_disk_space_used_GB_chunks)

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

    def max_memory_used(self):
        res = self.client.get_metric_statistics(
            Namespace='System/Linux',
            MetricName='MemoryUsed',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Average'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Megabytes'
        )
        x = [r['Average'] for r in res['Datapoints']]
        return(max(x) if x else '')

    def min_memory_available(self):
        res = self.client.get_metric_statistics(
            Namespace='System/Linux',
            MetricName='MemoryAvailable',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Average'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Megabytes'
        )
        x = [r['Average'] for r in res['Datapoints']]
        return(min(x) if x else '')

    def max_cpu_utilization(self):
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
        x = [r['Maximum'] for r in res['Datapoints']]
        return(max(x) if x else '')

    def max_disk_space_utilization(self):
        res = self.client.get_metric_statistics(
            Namespace='System/Linux',
            MetricName='DiskSpaceUtilization',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': self.instance_id},
                {'Name': 'MountPath', 'Value': '/data1'},
                {'Name': 'Filesystem', 'Value': self.filesystem}
            ],
            Period=60,
            Statistics=['Average'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Percent'
        )
        x = [r['Average'] for r in res['Datapoints']]
        return(max(x) if x else '')

    def max_disk_space_used(self):
        res = self.client.get_metric_statistics(
            Namespace='System/Linux',
            MetricName='DiskSpaceUsed',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': self.instance_id},
                {'Name': 'MountPath', 'Value': '/data1'},
                {'Name': 'Filesystem', 'Value': self.filesystem}
            ],
            Period=60,
            Statistics=['Average'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Gigabytes'
        )
        x = [r['Average'] for r in res['Datapoints']]
        return(max(x) if x else '')
