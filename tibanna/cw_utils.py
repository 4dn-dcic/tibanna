import boto3, os
from . import create_logger
from .utils import (
    upload,
    read_s3,
    put_object_s3
)
from .top import Top
from .vars import (
    AWS_REGION,
    EBS_MOUNT_POINT,
    S3_ENCRYT_KEY_ID
)
from datetime import datetime
from datetime import timedelta
import json, math


logger = create_logger(__name__)


class TibannaResource(object):
    """class handling cloudwatch metrics for cpu / memory /disk space
    and top command metrics for cpu and memory per process.
    """

    timestamp_format = '%Y-%m-%d %H:%M:%S'
    report_title = 'Tibanna Metrics'

    @classmethod
    def convert_timestamp_to_datetime(cls, timestamp):
        return datetime.strptime(timestamp, cls.timestamp_format)

    def __init__(self, instance_id, filesystem, starttime, endtime=datetime.utcnow(), cost_estimate = 0.0, cost_estimate_type = "NA"):
        """All the Cloudwatch metrics are retrieved and stored at the initialization.
        :param instance_id: e.g. 'i-0167a6c2d25ce5822'
        :param filesystem: e.g. "/dev/xvdb", "/dev/nvme1n1"
        """
        self.instance_id = instance_id
        self.filesystem = filesystem
        self.client = boto3.client('cloudwatch', region_name=AWS_REGION)
        # get resource metrics
        nTimeChunks = (endtime - starttime) / timedelta(days=1)
        # self.total_minutes = (endtime - starttime) / timedelta(minutes=1)
        if round(nTimeChunks) < nTimeChunks:
            nTimeChunks = round(nTimeChunks) + 1
        else:
            nTimeChunks = round(nTimeChunks)
        logger.info("Spliting run time into %s chunks" % str(nTimeChunks))
        self.starttimes = [starttime + timedelta(days=k) for k in range(0, nTimeChunks)]
        self.endtimes = [starttime + timedelta(days=k+1) for k in range(0, nTimeChunks)]
        self.start = starttime.replace(microsecond=0) # initial starttime for the window requested
        self.end = endtime.replace(microsecond=0) # initial endtime for the window requested
        self.nTimeChunks = nTimeChunks
        self.list_files = []
        self.cost_estimate = cost_estimate
        self.cost_estimate_type = cost_estimate_type
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
        max_ebs_read_chunks = []
        for i in range(0, nTimeChunks):
            self.starttime = self.starttimes[i]
            self.endtime = self.endtimes[i]
            max_mem_used_MB_chunks.append(self.max_memory_used())
            min_mem_available_MB_chunks.append(self.min_memory_available())
            max_cpu_utilization_percent_chunks.append(self.max_cpu_utilization())
            max_disk_space_utilization_percent_chunks.append(self.max_disk_space_utilization())
            max_disk_space_used_GB_chunks.append(self.max_disk_space_used())
            max_ebs_read_chunks.append(self.max_ebs_read())
        self.max_mem_used_MB = self.choose_max(max_mem_used_MB_chunks)
        self.min_mem_available_MB = self.choose_min(min_mem_available_MB_chunks)
        if self.max_mem_used_MB:
            self.total_mem_MB = self.max_mem_used_MB + self.min_mem_available_MB
            self.max_mem_utilization_percent = self.max_mem_used_MB / self.total_mem_MB * 100
        else:
            self.total_mem_MB = ''
            self.max_mem_utilization_percent = ''
        self.max_cpu_utilization_percent = self.choose_max(max_cpu_utilization_percent_chunks)
        self.max_disk_space_utilization_percent = self.choose_max(max_disk_space_utilization_percent_chunks)
        self.max_disk_space_used_GB = self.choose_max(max_disk_space_used_GB_chunks)
        # this following one is used to detect file copying while CPU utilization is near zero
        self.max_ebs_read_bytes = self.choose_max(max_ebs_read_chunks)

    def plot_metrics(self, instance_type, directory='.', top_content=''):
        """plot full metrics across all time chunks.
        AWS allows only 1440 data points at a time
        which corresponds to 24 hours at 1min interval,
        so we have to split them into chunks.
        :param top_content: content of the <job_id>.top in the str format, used for plotting top metrics.
        """
        max_mem_utilization_percent_chunks_all_pts = []
        max_mem_used_MB_chunks_all_pts = []
        min_mem_available_MB_chunks_all_pts = []
        max_cpu_utilization_percent_chunks_all_pts = []
        max_disk_space_utilization_percent_chunks_all_pts = []
        max_disk_space_used_GB_chunks_all_pts = []
        for i in range(0, self.nTimeChunks):
            self.starttime = self.starttimes[i]
            self.endtime = self.endtimes[i]
            # saving all points for the chunck
            max_mem_utilization_percent_chunks_all_pts.append(self.max_memory_utilization_all_pts())
            max_mem_used_MB_chunks_all_pts.append(self.max_memory_used_all_pts())
            min_mem_available_MB_chunks_all_pts.append(self.min_memory_available_all_pts())
            max_cpu_utilization_percent_chunks_all_pts.append(self.max_cpu_utilization_all_pts())
            max_disk_space_utilization_percent_chunks_all_pts.append(self.max_disk_space_utilization_all_pts())
            max_disk_space_used_GB_chunks_all_pts.append(self.max_disk_space_used_all_pts())
        # writing values as tsv
        input_dict ={
            'max_mem_used_MB': max_mem_used_MB_chunks_all_pts,
            'min_mem_available_MB': min_mem_available_MB_chunks_all_pts,
            'max_disk_space_used_GB': max_disk_space_used_GB_chunks_all_pts,
            'max_mem_utilization_percent': max_mem_utilization_percent_chunks_all_pts,
            'max_disk_space_utilization_percent': max_disk_space_utilization_percent_chunks_all_pts,
            'max_cpu_utilization_percent': max_cpu_utilization_percent_chunks_all_pts
        }

        self.list_files.extend(self.write_top_tsvs(directory, top_content))
        self.list_files.append(self.write_tsv(directory, **input_dict))
        self.list_files.append(self.write_metrics(instance_type, directory))
        # writing html
        self.list_files.append(self.write_html(instance_type, directory))

    def upload(self, bucket, prefix='', lock=True):
        logger.debug("list_files: " + str(self.list_files))
        for f in self.list_files:
            upload(f, bucket, prefix,
                   encrypt_s3_upload=S3_ENCRYT_KEY_ID is not None,
                   kms_key_id=S3_ENCRYT_KEY_ID)
        if lock:
            upload(None, bucket, os.path.join(prefix, 'lock'),
                   encrypt_s3_upload=S3_ENCRYT_KEY_ID is not None,
                   kms_key_id=S3_ENCRYT_KEY_ID)

    @staticmethod
    def choose_max(x):
        """given a list of values that may include None, 0 or an empty string,
        chooses a positive nonzero maximum. (e.g. [0,1,2,None,3] => 3)
        if no positive nonzero value exists in the list, returns an empty string."""
        return TibannaResource.get_max(list(filter(lambda x:x, x)))

    @staticmethod
    def choose_min(x):
        """given a list of values that may include None, 0 or an empty string,
        chooses a nonzero minimum. (e.g. [0,1,2,None,3] => 1)
        if no nonzero value exists in the list, returns an empty string."""
        return TibannaResource.get_min(list(filter(lambda x:x, x)))

    @staticmethod
    def get_max(x):
        """given a list of values, returns maximum value,
        but if the list is empty, returns an empty string"""
        return(max(x) if x else '')

    @staticmethod
    def get_min(x):
        """given a list of values, returns miminim value,
        but if the list is empty, returns an empty string"""
        return(min(x) if x else '')

    def as_dict(self):
        d = self.__dict__.copy()
        logger.debug("original dict: " + str(d))
        del(d['client'])
        del(d['starttimes'])
        del(d['endtimes'])
        del(d['starttime'])
        del(d['endtime'])
        del(d['filesystem'])
        del(d['instance_id'])
        # del(d['total_minutes'])
        del(d['start'])
        del(d['end'])
        del(d['nTimeChunks'])
        del(d['list_files'])
        return(d)

    # def as_table(self):
    #    d = self.as_dict()
    #    return(pd.DataFrame(d.items(), columns=['metric', 'value']))

    # functions that returns only max or min (backward compatible)
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

    def max_ebs_read(self):
        return(self.get_max(self.max_ebs_read_used_all_pts()))

    # functions that returns all points
    def max_memory_utilization_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='CWAgent',
            MetricName='mem_used_percent',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Percent'
        )
        pts = [(r['Maximum'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

    def max_memory_used_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='CWAgent',
            MetricName='mem_used',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Bytes'
        )
        pts = [(r['Maximum']/math.pow(1024, 2), r['Timestamp']) for r in res['Datapoints']] # get values in MB
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

    def min_memory_available_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='CWAgent',
            MetricName='mem_available',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Minimum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Bytes'
        )
        pts = [(r['Minimum']/math.pow(1024, 2), r['Timestamp']) for r in res['Datapoints']] # get values in MB
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

    def max_cpu_utilization_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='CWAgent',
            MetricName='cpu_usage_active',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Percent'
        )
        pts = [(r['Maximum'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

    def max_disk_space_utilization_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='CWAgent',
            MetricName='disk_used_percent',
            Dimensions=[{
              'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Percent'
        )
        pts = [(r['Maximum'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

    def max_disk_space_used_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='CWAgent',
            MetricName='disk_used',
            Dimensions=[{
              'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60,
            Statistics=['Maximum'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Bytes'
        )
        pts = [(r['Maximum']/math.pow(1024, 3), r['Timestamp']) for r in res['Datapoints']] # we want it in GB
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

    def max_ebs_read_used_all_pts(self):
        res = self.client.get_metric_statistics(
            Namespace='CWAgent',
            MetricName='diskio_read_bytes',
            Dimensions=[{
                'Name': 'InstanceId', 'Value': self.instance_id
            }],
            Period=60*5,
            Statistics=['Average'],
            StartTime=self.starttime,
            EndTime=self.endtime,
            Unit='Bytes'
        )
        pts = [(r['Average'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

    
    @staticmethod
    def extract_metrics_data(file_contents):
      """
      This function takes a file contents string and parses it column wise.
      It returns the header and the data in a way that can be injected into JS code
      `data` is a Python dict, that contains all that data for later processing
      outside of this function.
      """
      columns, data = [], {}
      columns_js, data_js = "[]", "[]"

      for idx, line in enumerate(file_contents.rstrip().split('\n')):
          if idx == 0:
              for k,col in enumerate(line.split('\t')):
                  columns.append(col)
                  data[col] = []
          else:
              for k, col in enumerate(line.split('\t')):
                  try:
                      float(col) # check if it's a number, still add it as string though
                      data[columns[k]].append(col)
                  except ValueError:
                      logger.info("Cannot convert %s to float in column %s" % (col, columns[k]))
                      continue

      columns.pop(0) # Remove the 'interval' column
      if len(columns)>0:
          columns_js = "["+(",".join(columns))+"]"
          data_js = "["
          for col in columns:
              data_js += "[" + (",".join(data[col])) + "],"
          data_js = data_js[:-1] # remove the last ,
          data_js += "]"

      return columns_js, columns, data_js, data

    @staticmethod
    def format_metrics_tsv_data(metrics_data):
        max_mem_used_MB = [str(k) for k in metrics_data['max_mem_used_MB']]
        max_mem_used_MB_js = "[" + (",".join(max_mem_used_MB)) + "]"
        min_mem_available_MB = [str(k) for k in metrics_data['min_mem_available_MB']]
        min_mem_available_MB_js = "[" + (",".join(min_mem_available_MB)) + "]"
        max_disk_space_used_GB = [str(k) for k in metrics_data['max_disk_space_used_GB']]
        max_disk_space_used_GB_js = "[" + (",".join(max_disk_space_used_GB)) + "]"

        max_mem_utilization_percent = [str(k) for k in metrics_data['max_mem_utilization_percent']]
        max_mem_utilization_percent_js = "[" + (",".join(max_mem_utilization_percent)) + "]"
        max_disk_space_utilization_percent = [str(k) for k in metrics_data['max_disk_space_utilization_percent']]
        max_disk_space_utilization_percent_js = "[" + (",".join(max_disk_space_utilization_percent)) + "]"
        max_cpu_utilization_percent = [str(k) for k in metrics_data['max_cpu_utilization_percent']]
        max_cpu_utilization_percent_js = "[" + (",".join(max_cpu_utilization_percent)) + "]"

        return (
            max_mem_used_MB_js,
            min_mem_available_MB_js,
            max_disk_space_used_GB_js,
            max_mem_utilization_percent_js,
            max_disk_space_utilization_percent_js,
            max_cpu_utilization_percent_js,
        )

    # functions to create reports and html
    def write_html(self, instance_type, directory):
        self.check_mkdir(directory)
        filename = directory + '/' + 'metrics.html'
        cost_estimate = '---' if self.cost_estimate == 0.0 else "{:.5f}".format(self.cost_estimate)
        
        metrics_contents = ""
        with open(directory + '/' + 'metrics.tsv') as f:
          metrics_contents = f.read()
        (
            metrics_col_js,
            metrics_col,
            metrics_data_js,
            metrics_data,
        ) = self.extract_metrics_data(metrics_contents)
        
        (
          max_mem_used_MB_js,
          min_mem_available_MB_js,
          max_disk_space_used_GB_js,
          max_mem_utilization_percent_js,
          max_disk_space_utilization_percent_js,
          max_cpu_utilization_percent_js,
        ) = self.format_metrics_tsv_data(metrics_data)
        
        top_cpu_contents = ""
        with open(directory + '/' + 'top_cpu.tsv') as f:
          top_cpu_contents = f.read()
        cpu_columns_js, cpu_columns, cpu_data_js, cpu_data = self.extract_metrics_data(top_cpu_contents)

        top_mem_contents = ""
        with open(directory + '/' + 'top_mem.tsv') as f:
          top_mem_contents = f.read()
        mem_columns_js, mem_columns, mem_data_js, mem_data = self.extract_metrics_data(top_mem_contents)

        with open(filename, 'w') as fo:
            fo.write(self.create_html() % (self.report_title, instance_type,
                             str(self.max_mem_used_MB), str(self.min_mem_available_MB), str(self.max_disk_space_used_GB),
                             str(self.max_mem_utilization_percent), str(self.max_cpu_utilization_percent),
                             str(self.max_disk_space_utilization_percent),
                             '---', # cost placeholder for now
                             cost_estimate, self.cost_estimate_type,
                             str(self.start), str(self.end), str(self.end - self.start),
                             max_mem_used_MB_js, min_mem_available_MB_js, max_disk_space_used_GB_js,
                             max_mem_utilization_percent_js, max_disk_space_utilization_percent_js, max_cpu_utilization_percent_js,
                             cpu_columns_js, cpu_data_js,
                             mem_columns_js, mem_data_js
                            )
                    )
        return(filename)

    @classmethod
    def update_html(cls, bucket, prefix, directory='.', upload_new=True):
        # reading tabel parameters from metrics_report.tsv
        read_file = read_s3(bucket, os.path.join(prefix, 'metrics_report.tsv'))
        d = {} # read the values into d
        for line in read_file.rstrip().split('\n'):
            k, v = line.split('\t')
            d.setdefault(k, v) # everything is string now
        # times into datetime objects
        starttime = cls.convert_timestamp_to_datetime(d['Start_Time'])
        try:
            endtime = cls.convert_timestamp_to_datetime(d['End_Time'])
        except: # temporary fix for retrocompatibility
            if 'End_time' in d:
                endtime = cls.convert_timestamp_to_datetime(d['End_time'])
            else:
                endtime = cls.convert_timestamp_to_datetime(d['Time_of_Request'])
        cost = d['Cost'] if 'Cost' in d else '---'
        estimated_cost = (float)(d['Estimated_Cost']) if 'Estimated_Cost' in d else 0.0
        estimated_cost = str(estimated_cost) if estimated_cost > 0.0 else '---'
        cost_estimate_type = d['Estimated_Cost_Type'] if 'Estimated_Cost_Type' in d else "NA"
        instance = d['Instance_Type'] if 'Instance_Type' in d else '---'

        metrics_contents = read_s3(bucket, os.path.join(prefix, 'metrics.tsv'))
        (
            metrics_col_js,
            cpu_metrics_col,
            metrics_data_js,
            metrics_data,
        ) = TibannaResource.extract_metrics_data(metrics_contents)
        
        (
          max_mem_used_MB_js,
          min_mem_available_MB_js,
          max_disk_space_used_GB_js,
          max_mem_utilization_percent_js,
          max_disk_space_utilization_percent_js,
          max_cpu_utilization_percent_js,
        ) = TibannaResource.format_metrics_tsv_data(metrics_data)

        top_cpu_contents = read_s3(bucket, os.path.join(prefix, 'top_cpu.tsv'))
        cpu_columns_js, cpu_columns, cpu_data_js, cpu_data = TibannaResource.extract_metrics_data(top_cpu_contents)

        top_mem_contents = read_s3(bucket, os.path.join(prefix, 'top_mem.tsv'))
        mem_columns_js, mem_columns, mem_data_js, mem_data = TibannaResource.extract_metrics_data(top_mem_contents)

        # writing
        html_content = cls.create_html() % (cls.report_title, instance,
                             d['Maximum_Memory_Used_Mb'], d['Minimum_Memory_Available_Mb'], d['Maximum_Disk_Used_Gb'],
                             d['Maximum_Memory_Utilization'], d['Maximum_CPU_Utilization'], d['Maximum_Disk_Utilization'],
                             cost,
                             estimated_cost, cost_estimate_type,
                             str(starttime), str(endtime), str(endtime-starttime),
                             max_mem_used_MB_js, min_mem_available_MB_js, max_disk_space_used_GB_js,
                             max_mem_utilization_percent_js, max_disk_space_utilization_percent_js, max_cpu_utilization_percent_js,
                             cpu_columns_js, cpu_data_js,
                             mem_columns_js, mem_data_js
                            )
        s3_key = os.path.join(prefix, 'metrics.html')
        if S3_ENCRYT_KEY_ID:
            put_object_s3(content=html_content, key=s3_key, bucket=bucket,
                          encrypt_s3_upload=True, kms_key_id=S3_ENCRYT_KEY_ID)
        else:
            put_object_s3(content=html_content, key=s3_key, bucket=bucket)

    @staticmethod
    def write_top_tsvs(directory, top_content):
        TibannaResource.check_mkdir(directory)
        top_obj = Top(top_content)
        top_obj.digest()
        cpu_filename = directory + '/' + 'top_cpu.tsv'
        mem_filename = directory + '/' + 'top_mem.tsv'
        top_obj.write_to_csv(cpu_filename, delimiter='\t', metric='cpu', colname_for_timestamps='interval', base=1)
        top_obj.write_to_csv(mem_filename, delimiter='\t', metric='mem', colname_for_timestamps='interval', base=1)
        return [cpu_filename, mem_filename]

    def write_tsv(self, directory, **kwargs): # kwargs, key: (chunks_all_pts, interval), interval is 1 or 5 min
        self.check_mkdir(directory)
        filename = directory + '/' + 'metrics.tsv'
        with open(filename, 'w') as fo:
            # preparing data and writing header
            data_unpacked = []
            for i, (key, arg) in enumerate(kwargs.items()):
                if i == 0:
                    fo.write('interval\t' + key)
                else:
                    fo.write('\t' + key)
                tmp = []
                [tmp.extend(a) for a in arg]
                data_unpacked.append(tmp[:])
                
            fo.write('\n')
            # writing table
            for i in range(len(data_unpacked[0])):
                fo.write(str(i + 1))
                for data in data_unpacked:
                    try:
                        fo.write('\t' + str(data[i]))
                    except:
                        fo.write('\t' + '-')
                fo.write('\n')
        return(filename)

    def write_metrics(self, instance_type, directory):
        self.check_mkdir(directory)
        filename = directory + '/' + 'metrics_report.tsv'
        with open(filename, 'w') as fo:
            fo.write('Metric\tValue\n')
            fo.write('Maximum_Memory_Used_Mb' + '\t' + str(self.max_mem_used_MB) + '\n')
            fo.write('Minimum_Memory_Available_Mb' + '\t' + str(self.min_mem_available_MB) + '\n')
            fo.write('Maximum_Disk_Used_Gb' + '\t' + str(self.max_disk_space_used_GB) + '\n')
            fo.write('Maximum_Memory_Utilization' + '\t' + str(self.max_mem_utilization_percent) + '\n')
            fo.write('Maximum_CPU_Utilization' + '\t' + str(self.max_cpu_utilization_percent) + '\n')
            fo.write('Maximum_Disk_Utilization' + '\t' + str(self.max_disk_space_utilization_percent) + '\n')
            fo.write('Start_Time' + '\t' + str(self.start) + '\n')
            fo.write('End_Time' + '\t' + str(self.end) + '\n')
            fo.write('Instance_Type' + '\t' + instance_type + '\n')
            fo.write('Estimated_Cost' + '\t' + str(self.cost_estimate) + '\n')
            fo.write('Estimated_Cost_Type' + '\t' + str(self.cost_estimate_type) + '\n')
        return(filename)

    @staticmethod
    def check_mkdir(directory):
        if not os.path.exists(directory):
            os.makedirs(directory)

    @classmethod
    def create_html(cls):
        html = """\
                <!DOCTYPE html>
                <meta charset="utf-8">
                <link href="https://fonts.googleapis.com/css?family=Source+Sans+Pro:200,300,400,600,700,900,300i,400i,600i" rel="stylesheet"/>
                <style type="text/css">
                :root {
                   font-size: 16px
                }
                body{ margin: 0; }
                /* Basic Styling with CSS */
                h1 {
                  font-family: "Source Sans Pro", sans-serif;
                  color: #D3DADF;
                  font-weight: lighter;
                  font-size: 1.7rem;
                  padding-left: 50px;
                }
                h2 {
                  text-align: center;
                  font-family: "Source Sans Pro", sans-serif;
                  font-size: 1rem;
                  padding: 13px;
                  color: #ffffff;
                  font-weight: normal;
                }
                p {
                  font-size: .9rem;
                  font-family: "Source Sans Pro", sans-serif;
                }
                text {
                  font-family: "Source Sans Pro", sans-serif;
                  font-weight: normal;
                  font-size: .825rem;
                }
                table {
                  font-family: "Source Sans Pro", sans-serif;
                  width: 40%%;
                  border-collapse: collapse;
                }
                .right {
                  text-align: right;
                }
                .center {
                  text-align: center;
                }
                .left {
                  text-align: left;
                }
                td {
                  border-bottom: 1px solid #dddddd;
                  padding: 11px;
                  font-size: .925rem;
                }
                th {
                  padding: 13px;
                  font-size: 1rem;
                  background-color: #2C6088;
                  color: #ffffff;
                  font-weight: normal;
                }
                div {
                  display: block;
                  height: 500px;
                  width: 100%%;
                }
                .logo {
                  max-height: 81px;
                  width: 100%%;
                  background-color: #20445E;
                  display: flex;
                  align-items: center;
                }
                .header {
                  margin-left: auto;
                  margin-right: auto;
                  height: auto;
                  width: 85%%;
                  background-color: #2C6088;
                }
                .barplot {
                  height: 300px;
                }
                .barplot_legend {
                  height: 350px;
                }
                /* Style the lines by removing the fill and applying a stroke */
                .line {
                    fill: none;
                    stroke: #cc0000;
                    stroke-width: 2;
                }
                .overlay {
                  fill: none;
                  pointer-events: all;
                }
                /* Legend */
                .data-name {
                    margin: 0 !important;
                }
                .key-dot {
                    display: inline-block;
                    height: 7px;
                    margin-right: .5em;
                    width: 7px;
                }
                .mem { background: #2008FF;}
                .cpu { background: #800380;}
                .disk { background: #218000;
                }
                #legend{
                    overflow:hidden;
                }
                .legend {
                    position: relative;
                    float:left;
                    height: auto;
                    width: 100px;
                }
                .legend-wrapper {
                    margin-left: 150px;
                    height: auto;
                }
                /* Grid */
                .grid line {
                  stroke: #e6f2ff;
                  stroke-opacity: 0.9;
                  shape-rendering: crispEdges;
                }
                .grid path {
                  stroke-width: 0;
                }
                </style>
                <!-- Body tag is where we will append our SVG and SVG objects-->
                <body>
                    <div class="logo">
                      <h1>%s</h1>
                    </div></br></br>
                  <section>
                    </br>
                    <table align="center">
                      <tr>
                        <th colspan="2">General Information</th>
                      </tr>
                      <tr>
                        <td class="left">EC2 Instance Type</td>
                        <td class="center">%s</td>
                      </tr>
                    </table>
                    </br></br>
                    <table align="center">
                      <tr>
                        <th colspan="2">Metrics</th>
                      </tr>
                      <tr>
                        <td class="left">Maximum Memory Used [Mb]</td>
                        <td class="center">%s</td>
                      </tr>
                      <tr>
                        <td class="left">Minimum Memory Available [Mb]</td>
                        <td class="center">%s</td>
                      </tr>
                      <tr>
                        <td class="left">Maximum Disk Used (/data1) [Gb]</td>
                        <td class="center">%s</td>
                      </tr>
                      <tr>
                        <td class="left">Maximum Memory Utilization [%%]</td>
                        <td class="center">%s</td>
                      </tr>
                      <tr>
                        <td class="left">Maximum CPU Utilization [%%]</td>
                        <td class="center">%s</td>
                      </tr>
                      <tr>
                        <td class="left">Maximum Disk Utilization (/data1) [%%]</td>
                        <td class="center">%s</td>
                      </tr>
                      <tr>
                        <td class="left">Cost</td>
                        <td class="center">%s</td>
                      </tr>
                      <tr>
                        <td class="left">Cost (estimated) (USD)</td>
                        <td class="center">%s (%s)</td>
                      </tr>
                    </table>
                    </br></br>
                    <table align="center">
                      <tr>
                        <th class="left">Start Time [UTC]</th>
                        <th class="left">End Time [UTC]</th>
                        <th class="left">Total Time</th>
                      </tr>
                      <tr>
                        <td class="left">%s</td>
                        <td class="left">%s</td>
                        <td class="left">%s</td>
                      </tr>
                    </table>
                  </section>
                  </br></br>
                  <section>
                    <div class="header">
                      <h2>Resources Utilization</h2>
                    </div>
                      <div id="chart_percent">
                        <div class="legend-wrapper">
                            <div class="legend"> <p class="data-name"><span class="key-dot cpu"></span>CPU Utilization</p> </div>
                            <div class="legend"> <p class="data-name"><span class="key-dot mem"></span>Memory Utilization</p> </div>
                            <div class="legend"> <p class="data-name"><span class="key-dot disk"></span>Disk Utilization (/data1)</p> </div>
                        </div>
                      </div></br></br>
                    <div class="header">
                      <h2>Memory Usage</h2>
                    </div>
                      <div id="chart_max_mem"> </div>
                    <div class="header">
                      <h2>Memory Available</h2>
                    </div>
                      <div id="chart_min_mem"> </div>
                    <div class="header">
                      <h2>Disk Usage (/data1)</h2>
                    </div>
                      <div id="chart_disk"> </div>
                    <div class="header">
                      <h2>CPU Usage Per Process (from Top command)</h2>
                    </div>
                      <div class="barplot" id="bar_chart_cpu"> </div>
                      <div id="bar_chart_cpu_legend" class="barplot_legend"> </div>
                    <div class="header">
                      <h2>Memory Usage Per Process (from Top command)</h2>
                    </div>
                      <div class="barplot" id="bar_chart_mem"> </div>
                      <div id="bar_chart_mem_legend" class="barplot_legend"> </div>
                  </section>
                </body>
                <!-- Load in the d3 library -->
                <script src="https://d3js.org/d3.v5.min.js"></script>
                <script>
                //var onResize = _.debounce(function(){
                //  svgElem.innerHTML = '';
                //  line_plot();
                //});
                //window.onload = function(){
                //  window.addEventListener('resize', onResize);
                //}
                /* Functions definition */
                function make_x_gridlines(x, n) {
                  var n_l = 0
                  if (n < 1440) {
                    n_l = n / 10
                  } else { // runtime longer than a day
                    n_l = n / 60
                  }
                  return d3.axisBottom(x)
                        .ticks(n_l)
                }
                function make_y_gridlines(y, n) {
                  var n_l = 0
                  if (n <= 200) {
                    n_l = n / 10
                  } else if (n <= 500) {
                    n_l = n / 50
                  } else if (n <= 2000) {
                    n_l = n / 100
                  } else if (n <= 5000) {
                    n_l = n / 500
                  } else if (n <= 20000) {
                    n_l = n / 1000
                  } else {
                    n_l = n / 5000
                  }
                  return d3.axisLeft(y)
                        .ticks(n_l)
                }
                function percent_plot(data_array, div) { // data_array = [data_mem, data_disk, data_cpu]
                  // Get div dimensions
                  var div_width = document.getElementById(div).offsetWidth
                    , div_height = document.getElementById(div).offsetHeight;
                  // Use the margin convention practice
                  var margin = {top: 40, right: 150, bottom: 100, left: 150}
                    , width = div_width - margin.left - margin.right // Use the window's width
                    , height = div_height - margin.top - margin.bottom; // Use the window's height
                  // Dataset as y values
                  data_mem = data_array[0]
                  data_disk = data_array[1]
                  data_cpu = data_array[2]
                  // The number of datapoints
                  var n_data = data_mem.length;
                  var n = 0
                  if (n_data < 5) {
                    n = 5
                  } else {
                    n = n_data
                  }
                  var n_cpu = data_cpu.length;
                  // X scale will use the index of our data
                  var xScale = d3.scaleLinear()
                      .domain([0, n]) // input
                      .range([0, width]); // output
                  // X scale for CPU utilization
                  var xScale_cpu = d3.scaleLinear()
                      .domain([0, n_cpu]) // input
                      .range([0, width*(n_cpu)/(n)]); // output
                  // Y scale will use the randomly generate number
                  var yScale = d3.scaleLinear()
                      .domain([0, 100]) // input
                      .range([height, 0]); // output
                  // d3's line generator
                  var line = d3.line()
                      .x(function(d, i) { return xScale(i) + xScale(1); }) // set the x values for the line generator
                      .y(function(d) { return yScale(d.y); }) // set the y values for the line generator
                      //.curve(d3.curveMonotoneX) // apply smoothing to the line
                  // d3's line generator for CPU utilization
                  var line_cpu = d3.line()
                      .x(function(d, i) { return xScale_cpu(i) + xScale(1); }) // set the x values for the line generator
                      .y(function(d) { return yScale(d.y); }) // set the y values for the line generator
                      //.curve(d3.curveMonotoneX) // apply smoothing to the line
                  // An array of objects of length N. Each object has key -> value pair, the key being "y" and the value is a random number
                  var dataset_mem = d3.range(n_data).map(function(d) { return {"y": data_mem[d] } })
                  var dataset_disk = d3.range(n_data).map(function(d) { return {"y": data_disk[d] } })
                  var dataset_cpu = d3.range(n_cpu).map(function(d) { return {"y": data_cpu[d] } })
                  // Add the SVG to the page
                  var svg = d3.select("#" + div).append("svg")
                      .attr("width", width + margin.left + margin.right)
                      .attr("height", height + margin.top + margin.bottom)
                    .append("g")
                      .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
                  // Add the X gridlines
                  svg.append("g")
                      .attr("class", "grid")
                      .attr("transform", "translate(0," + height + ")")
                      .call(make_x_gridlines(xScale, n)
                          .tickSize(-height)
                          .tickFormat("")
                      )
                  // Add the Y gridlines
                  svg.append("g")
                      .attr("class", "grid")
                      .call(make_y_gridlines(yScale, 100)
                          .tickSize(-width)
                          .tickFormat("")
                      )
                  // Call the x axis in a group tag
                  svg.append("g")
                      .attr("class", "x axis")
                      .attr("transform", "translate(0," + height + ")")
                      .call(d3.axisBottom(xScale)); // Create an axis component with d3.axisBottom
                  // Call the y axis in a group tag
                  svg.append("g")
                      .attr("class", "y axis")
                      .call(d3.axisLeft(yScale)); // Create an axis component with d3.axisLeft
                  // Append the path, bind the data, and call the line generator
                  svg.append("path")
                      .datum(dataset_mem) // Binds data to the line
                      .attr("class", "line") // Assign a class for styling
                      .style("stroke", "blue")
                      .attr("d", line); // Calls the line generator
                  // Append the path, bind the data, and call the line generator
                  svg.append("path")
                      .datum(dataset_disk) // Binds data to the line
                      .attr("class", "line") // Assign a class for styling
                      .style("stroke", "green")
                      .attr("d", line); // Calls the line generator
                  // Append the path, bind the data, and call the line generator
                  svg.append("path")
                      .datum(dataset_cpu) // Binds data to the line
                      .attr("class", "line") // Assign a class for styling
                      .style("stroke", "purple")
                      .attr("d", line_cpu); // Calls the line generator
                  svg.append("text")
                      .attr("transform", "translate(" + (width / 2) + " ," + (height + margin.bottom - margin.bottom / 2) + ")")
                      .style("text-anchor", "middle")
                      .text("Time [min]");
                  svg.append("text")
                      .attr("transform", "rotate(-90)")
                      .attr("y", 0 - margin.left + margin.left / 2)
                      .attr("x",0 - (height / 2))
                      .attr("dy", "1em")
                      .style("text-anchor", "middle")
                      .text('Percentage [%%]');
                }
                function line_plot(data, div, axis_label) {
                  // Get div dimensions
                  var div_width = document.getElementById(div).offsetWidth
                    , div_height = document.getElementById(div).offsetHeight;
                  // Use the margin convention practice
                  var margin = {top: 20, right: 150, bottom: 100, left: 150}
                    , width = div_width - margin.left - margin.right // Use the window's width
                    , height = div_height - margin.top - margin.bottom; // Use the window's height
                  // The number of datapoints
                  var n_data = data.length;
                  var n = 0
                  if (n_data < 5) {
                    n = 5
                  } else {
                    n = n_data
                  }
                  // X scale will use the index of our data
                  var xScale = d3.scaleLinear()
                      .domain([0, n]) // input
                      .range([0, width]); // output
                  // Y scale will use the randomly generate number
                  var yScale = d3.scaleLinear()
                      .domain([0, d3.max(data)]) // input
                      .range([height, 0]); // output
                  // d3's line generator
                  var line = d3.line()
                      .x(function(d, i) { return xScale(i) + xScale(1); }) // set the x values for the line generator
                      .y(function(d) { return yScale(d.y); }) // set the y values for the line generator
                      //.curve(d3.curveMonotoneX) // apply smoothing to the line
                  // An array of objects of length N. Each object has key -> value pair, the key being "y" and the value is a random number
                  var dataset = d3.range(n_data).map(function(d) { return {"y": data[d] } })
                  // Add the SVG to the page
                  var svg = d3.select("#" + div).append("svg")
                      .attr("width", width + margin.left + margin.right)
                      .attr("height", height + margin.top + margin.bottom)
                    .append("g")
                      .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
                  // Add the X gridlines
                  svg.append("g")
                      .attr("class", "grid")
                      .attr("transform", "translate(0," + height + ")")
                      .call(make_x_gridlines(xScale, n)
                          .tickSize(-height)
                          .tickFormat("")
                      )
                  // Add the Y gridlines
                  svg.append("g")
                      .attr("class", "grid")
                      .call(make_y_gridlines(yScale, d3.max(data))
                          .tickSize(-width)
                          .tickFormat("")
                      )
                  // Call the x axis in a group tag
                  svg.append("g")
                      .attr("class", "x axis")
                      .attr("transform", "translate(0," + height + ")")
                      .call(d3.axisBottom(xScale)); // Create an axis component with d3.axisBottom
                  // Call the y axis in a group tag
                  svg.append("g")
                      .attr("class", "y axis")
                      .call(d3.axisLeft(yScale)); // Create an axis component with d3.axisLeft
                  // Append the path, bind the data, and call the line generator
                  svg.append("path")
                      .datum(dataset) // Binds data to the line
                      .attr("class", "line") // Assign a class for styling
                      .attr("d", line); // Calls the line generator
                  svg.append("text")
                      .attr("transform", "translate(" + (width / 2) + " ," + (height + margin.bottom - margin.bottom / 2) + ")")
                      .style("text-anchor", "middle")
                      .text("Time [min]");
                  svg.append("text")
                      .attr("transform", "rotate(-90)")
                      .attr("y", 0 - margin.left + margin.left / 2)
                      .attr("x",0 - (height / 2))
                      .attr("dy", "1em")
                      .style("text-anchor", "middle")
                      .text(axis_label);
                }
                var barplot_colors = ['black', 'red', 'green', 'blue', 'magenta', 'yellow', 'cyan',
                                      'pink', 'mediumslateblue', 'maroon', 'orange',
                                      'gray', 'palegreen', 'mediumvioletred', 'deepskyblue',
                                      'rosybrown', 'lightgrey', 'indigo', 'cornflowerblue']
                function bar_plot(data_array, div, axis_label) {
                  // Get div dimensions
                  var div_width = document.getElementById(div).offsetWidth
                    , div_height = document.getElementById(div).offsetHeight;
                  // Use the margin convention practice
                  var margin = {top: 20, right: 150, bottom: 100, left: 150}
                    , width = div_width - margin.left - margin.right // Use the window's width
                    , height = div_height - margin.top - margin.bottom; // Use the window's height
                  // number of different colors (also number of columns to visualize together)
                  var n_cols = data_array.length
                  // The number of datapoints
                  var n_data = data_array[0].length;
                  var n = 0
                  if (n_data < 5) {
                    n = 5
                  } else {
                    n = n_data
                  }
                  // sum for each timepoint, to calculate y scale
                  sum_array = d3.range(n_data).map(function(d) {
                      var sum = 0
                      for( col=0; col<n_cols; col++) sum += data_array[col][d]
                      return sum
                  })
                  // X scale will use the index of our data
                  var xScale = d3.scaleLinear()
                      .domain([0, n]) // input
                      .range([0, width])  // output
                  // Y scale will use the randomly generate number
                  var yScale = d3.scaleLinear()
                      .domain([0, d3.max(sum_array)]) // input
                      .range([height, 0]); // output
                  // An array of objects of length N. Each object has key -> value pair, the key being "y" and the value is a random number
                  // Add the SVG to the page
                  var svg = d3.select("#" + div).append("svg")
                      .attr("width", width + margin.left + margin.right)
                      .attr("height", height + margin.top + margin.bottom)
                    .append("g")
                      .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
                  // Add the X gridlines
                  svg.append("g")
                      .attr("class", "grid")
                      .attr("transform", "translate(0," + height + ")")
                      .call(make_x_gridlines(xScale, n)
                          .tickSize(-height)
                          .tickFormat("")
                      )
                  // Add the Y gridlines
                  svg.append("g")
                      .attr("class", "grid")
                      .call(make_y_gridlines(yScale, d3.max(sum_array))
                          .tickSize(-width)
                          .tickFormat("")
                      )
                  // Call the x axis in a group tag
                  svg.append("g")
                      .attr("class", "x axis")
                      .attr("transform", "translate(0," + height + ")")
                      .call(d3.axisBottom(xScale)); // Create an axis component with d3.axisBottom
                  // Call the y axis in a group tag
                  svg.append("g")
                      .attr("class", "y axis")
                      .call(d3.axisLeft(yScale)); // Create an axis component with d3.axisLeft
                  // Add rectangles, bind the data
                  var data_array_cum = data_array  // dimension and index 0 should be the same
                  for( var col=0; col<n_cols; col++) {
                      if(col == 0) {
                          data_array_cum[col] = d3.range(n_data).map(function(d) { return data_array[col][d] })
                          var dataset = d3.range(n_data).map(function(d) { return {"prev_y": 0, "y": data_array_cum[col][d]} })
                      }
                      if(col > 0) {
                          data_array_cum[col] = d3.range(n_data).map(function(d) { return data_array_cum[col-1][d] + data_array[col][d] })
                          var dataset = d3.range(n_data).map(function(d) { return {"prev_y": data_array_cum[col-1][d], "y": data_array_cum[col][d]} })
                      }
                      //var dataset = d3.range(n_data).map(function(d) { return {"dy": data_array[col][d], "y": data_array_cum[col][d]} })
                      svg.selectAll(".bar")
                          .data(dataset)
                          .enter()
                          .append('rect')
                          .attr("class", "bar" + col)
                          .attr("fill", barplot_colors[col])
                          .attr('x', function(d, i) { return xScale(i) + xScale(1) - xScale(0.5); })
                          .attr('y', function(d) { return yScale(d.y); })
                          .attr('height', function(d) { return yScale(d.prev_y) - yScale(d.y); })
                          .attr('width', xScale(1));
                  }
                  svg.append("text")
                      .attr("transform", "translate(" + (width / 2) + " ," + (height + margin.bottom - margin.bottom / 2) + ")")
                      .style("text-anchor", "middle")
                      .text("Time [min]");
                  svg.append("text")
                      .attr("transform", "rotate(-90)")
                      .attr("y", 0 - margin.left + margin.left / 2)
                      .attr("x",0 - (height / 2))
                      .attr("dy", "1em")
                      .style("text-anchor", "middle")
                      .text(axis_label);
                }
                function bar_plot_legend(legend_text, div) {
                  // Get div dimensions
                  var div_width = document.getElementById(div).offsetWidth
                    , div_height = document.getElementById(div).offsetHeight;
                  // Use the margin convention practice
                  var margin = {top: 20, right: 150, bottom: 100, left: 150}
                    , width = div_width - margin.left - margin.right // Use the window's width
                    , height = div_height - margin.top - margin.bottom; // Use the window's height
                  // number of different colors (also number of columns to visualize together)
                  var n_cols = legend_text.length
                  // Add the SVG to the page
                  var svg = d3.select("#" + div).append("svg")
                      .attr("width", width + margin.left + margin.right)
                      .attr("height", height + margin.top + margin.bottom)
                    .append("g")
                      .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
                  for( var col=0; col<n_cols; col++) {
                      var legend_y = 20 * col
                      var legend_symbol_radius = 5
                      var legend_x = 2 * legend_symbol_radius + 10
                      // legend text
                      svg.append("text")
                          .attr("transform", "translate(" + legend_x + " ," + legend_y + ")")
                          .attr("text-anchor", "left")
                          .text(legend_text[col])
                      // legend circles with colors
                      svg.append("circle")
                          .attr("cy", legend_y - legend_symbol_radius)
                          .attr("cx", legend_symbol_radius)
                          .attr("r", legend_symbol_radius)
                          .style("fill", barplot_colors[col])
                  }
                }
                /* Reading data and Plotting */
                line_plot(%s, 'chart_max_mem', 'Memory used [Mb]');
                line_plot(%s, 'chart_min_mem', 'Memory available [Mb]');
                line_plot(%s, 'chart_disk', 'Disk space used [Gb]');

                var resources_utilization = [%s, %s, %s];
                percent_plot(resources_utilization, 'chart_percent');

                var cpu_columns = %s;
                var cpu_data = %s;
                bar_plot(cpu_data, 'bar_chart_cpu', 'Total CPU (%%) [100%% = 1 CPU]');
                bar_plot_legend(cpu_columns, 'bar_chart_cpu_legend');

                var mem_columns = %s;
                var mem_data = %s;
                bar_plot(mem_data, 'bar_chart_mem', 'Total Mem (%% total available memory)');
                bar_plot_legend(mem_columns, 'bar_chart_mem_legend');

                </script>\
            """
        return(html)
