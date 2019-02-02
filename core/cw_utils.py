import boto3
from core.utils import printlog
# import pandas as pd
# from datetime import datetime
# from datetime import timezone
# from datetime import timedelta

# instance_id = 'i-0167a6c2d25ce5822'
# filesystem = "/dev/xvdb"
# filesystem = "/dev/nvme1n1"


class TibannaResource(object):
    def __init__(self, instance_id, filesystem, starttime, endtime):
        self.instance_id = instance_id
        self.filesystem = filesystem
        self.starttime = starttime
        self.endtime = endtime
        self.client = boto3.client('cloudwatch', region_name='us-east-1')
        # get resource metrics
        self.max_mem_used_MB = self.max_memory_used()
        self.max_mem_available_MB = self.max_memory_available()
        if self.max_mem_used_MB:
            self.total_mem_MB = self.max_mem_used_MB + self.max_mem_available_MB
            self.max_mem_utilization_percent = self.max_mem_used_MB / self.total_mem_MB
        self.max_cpu_utilization_percent = self.max_cpu_utilization()
        self.max_disk_space_utilization_percent = self.max_disk_space_utilization()
        self.max_disk_space_used_GB = self.max_disk_space_used()

    def as_dict(self):
        d = self.__dict__.copy()
        printlog(d)
        del(d['client'])
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

    def max_memory_available(self):
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
            Period=60*20,
            Statistics=['Average'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Percent'
        )
        x = [r['Average'] for r in res['Datapoints']]
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
