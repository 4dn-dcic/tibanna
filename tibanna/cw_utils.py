import boto3
from tibanna.utils import (
    printlog,
    upload
)
# import pandas as pd
# from datetime import timezone
from datetime import datetime
from datetime import timedelta
# import matplotlib.pyplot as plt

# instance_id = 'i-0167a6c2d25ce5822'
# filesystem = "/dev/xvdb"
# filesystem = "/dev/nvme1n1"


class TibannaResource(object):
    def __init__(self, instance_id, filesystem, starttime, endtime=datetime.utcnow()):
        self.instance_id = instance_id
        self.filesystem = filesystem
        self.client = boto3.client('cloudwatch', region_name='us-east-1')
        # get resource metrics
        nTimeChunks = (endtime - starttime) / timedelta(days=1)
        # self.total_minutes = (endtime - starttime) / timedelta(minutes=1)
        if round(nTimeChunks) < nTimeChunks:
            nTimeChunks = round(nTimeChunks) + 1
        else:
            nTimeChunks = round(nTimeChunks)
        print("Spliting run time into %s chunks" % str(nTimeChunks))
        self.starttimes = [starttime + timedelta(days=k) for k in range(0, nTimeChunks)]
        self.endtimes = [starttime + timedelta(days=k+1) for k in range(0, nTimeChunks)]
        self.start = starttime.replace(microsecond=0) # initial starttime for the window requested
        self.end = endtime.replace(microsecond=0) # initial endtime for the window requested
        self.nTimeChunks = nTimeChunks
        self.list_files = []
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

    def plot_metrics(self, instance_type, directory='.'):
        """plot full metrics across all time chunks.
        AWS allows only 1440 data points at a time
        which corresponds to 24 hours at 1min interval,
        so we have to split them into chunks.
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
        # plots and writing html
        # self.list_files.append(self.plot_single(directory, max_mem_used_MB_chunks_all_pts, 'Memory used [Mb]', 'Memory Usage'))
        # self.list_files.append(self.plot_single(directory, min_mem_available_MB_chunks_all_pts, 'Memory available [Mb]', 'Memory Available'))
        # self.list_files.append(self.plot_single(directory, max_disk_space_used_GB_chunks_all_pts, 'Disk space used [Gb]', 'Disk Usage (/data1)'))
        # self.list_files.append(self.plot_percent(directory, max_mem_utilization_percent_chunks_all_pts, max_disk_space_utilization_percent_chunks_all_pts, max_cpu_utilization_percent_chunks_all_pts))
        self.list_files.append(self.create_html(instance_type, directory))
        # writing values as tsv
        input_dict ={
            'max_mem_used_MB': (max_mem_used_MB_chunks_all_pts, 1),
            'min_mem_available_MB': (min_mem_available_MB_chunks_all_pts, 1),
            'max_disk_space_used_GB': (max_disk_space_used_GB_chunks_all_pts, 1),
            'max_mem_utilization_percent': (max_mem_utilization_percent_chunks_all_pts, 1),
            'max_disk_space_utilization_percent': (max_disk_space_utilization_percent_chunks_all_pts, 1),
            'max_cpu_utilization_percent': (max_cpu_utilization_percent_chunks_all_pts, 5)
        }
        self.list_files.append(self.write_tsv(directory, **input_dict))
        self.list_files.append(self.write_metrics(instance_type, directory))

    def upload(self, bucket, prefix=''):
        for f in self.list_files:
            upload(f, bucket, prefix)

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
        pts = [(r['Maximum'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

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
        pts = [(r['Maximum'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

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
        pts = [(r['Minimum'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

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
        pts = [(r['Maximum'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

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
        pts = [(r['Maximum'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

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
        pts = [(r['Maximum'], r['Timestamp']) for r in res['Datapoints']]
        return[p[0] for p in sorted(pts, key=lambda x: x[1])]

    # # functions to plot
    # def plot_single(self, directory, chuncks_all_pts, ylabel, title):
    #     plt.ioff() # rendering off
    #     plt.figure(figsize=(40,10))
    #     # preparing and plotting data
    #     y = []
    #     [y.extend(chunck_all_pts) for chunck_all_pts in chuncks_all_pts]
    #     plt.plot(list(range(len(y))), y, '-o', linewidth=3, markersize=1.5)
    #     # formatting labels, axis and title
    #     plt.xlabel('Time [min]', fontsize=22, labelpad=30)
    #     plt.ylabel(ylabel, fontsize=22, labelpad=30)
    #     plt.xticks(fontsize=22)
    #     plt.yticks(fontsize=22)
    #     plt.ylim(ymin=0)
    #     plt.xlim(xmin=0 , xmax=self.total_minutes)
    #     plt.title(title, fontsize=30, pad=60, fontweight="bold")
    #     # formatting grid
    #     plt.minorticks_on()
    #     plt.grid(b=True, which='major', color='#666666', linestyle='-')
    #     plt.grid(b=True, which='minor', color='#999999', linestyle='--', alpha=0.3)
    #     # saving the plot
    #     filename = directory + '/' + '_'.join(ylabel.replace('[', '').replace(']', '').split()).lower() + '.png'
    #     plt.savefig(filename)
    #     plt.close(fig='all')
    #     # clearing plt
    #     plt.clf()
    #     return(filename)

    # def plot_percent(self, directory, mem_chuncks_all_pts, disk_chuncks_all_pts, cpu_chuncks_all_pts, title='Resources Utilization'):
    #     plt.ioff() # rendering off
    #     plt.figure(figsize=(40,12))
    #     # preparing and plotting data
    #     y_mem, y_disk, y_cpu = [], [], []
    #     [y_mem.extend(chunck_all_pts) for chunck_all_pts in mem_chuncks_all_pts]
    #     [y_disk.extend(chunck_all_pts) for chunck_all_pts in disk_chuncks_all_pts]
    #     [y_cpu.extend(chunck_all_pts) for chunck_all_pts in cpu_chuncks_all_pts]
    #     plt.plot(list(range(len(y_mem))), y_mem, '-o', linewidth=3, markersize=1.5, color='blue', label='Memory Utilization')
    #     plt.plot(list(range(len(y_disk))), y_disk, '-o', linewidth=3, markersize=1.5, color='purple', label='Disk Utilization')
    #     x_cpu = list(range(len(y_cpu)))
    #     plt.plot([x*5 for x in x_cpu], y_cpu, '-o', linewidth=3, markersize=1.5, color='green', label='CPU Utilization') #goes by 5
    #     # formatting labels, axis and title
    #     plt.xlabel('Time [min]', fontsize=22, labelpad=30)
    #     plt.ylabel('Percentage', fontsize=22, labelpad=30)
    #     plt.xticks(fontsize=22)
    #     plt.yticks(fontsize=22)
    #     plt.ylim(ymin=0, ymax=100)
    #     plt.xlim(xmin=0, xmax=self.total_minutes)
    #     plt.title(title, fontsize=30, pad=60, fontweight="bold")
    #     plt.legend(fontsize=22, loc='upper center', bbox_to_anchor=(0.81, -0.055), ncol=3)
    #     # formatting grid
    #     plt.minorticks_on()
    #     plt.grid(b=True, which='major', color='#666666', linestyle='-')
    #     plt.grid(b=True, which='minor', color='#999999', linestyle='--', alpha=0.3)
    #     # saving the plot
    #     filename = directory + '/' + 'utilization_mem_disk_cpu.png'
    #     plt.savefig(filename)
    #     plt.close(fig='all')
    #     # clearing plt
    #     plt.clf()
    #     return(filename)

    def create_html(self, instance_type, directory):
        filename = directory + '/' + 'metrics.html'
        with open(filename, 'w') as fo:
            html = """\
                    <!DOCTYPE html>
                    <meta charset="utf-8">
                    <style type="text/css">
                    /* Basic Styling with CSS */
                    h2 {
                      text-align: center;
                      font-family: "Times New Roman";
                      font-size: 19px;
                      padding: 10px;
                    }
                    p {
                      font-size: 14px;
                    }
                    table {
                      font-family: "Times New Roman";
                      width: 60%%;
                    }
                    td {
                      border: 1px solid #dddddd;
                      text-align: left;
                      padding: 8px;
                      font-size: 13px;
                    }
                    th {
                      border: 1px solid #dddddd;
                      text-align: left;
                      padding: 8px;
                      font-size: 15px;
                    }
                    tr:nth-child(even) {
                      background-color: #e6f2ff;
                    }
                    div {
                      display: block;
                      height: 500px;
                      width: 100%%;
                    }
                    .header {
                      margin-left: auto;
                      margin-right: auto;
                      height: auto;
                      width: 85%%;
                      background-color: #e6f2ff;
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
                    </style>
                    <!-- Body tag is where we will append our SVG and SVG objects-->
                    <body>
                      <section>
                        <div class="header">
                          <h2>Summary Metrics and Time</h2>
                        </div>
                        </br>
                        <table align="center">
                          <tr>
                            <th>Metric</th>
                            <th>Value</th>
                          </tr>
                          <tr>
                            <td>Maximum Memory Used [Mb]</td>
                            <td>%d</td>
                          </tr>
                          <tr>
                            <td>Minimum Memory Available [Mb]</td>
                            <td>%d</td>
                          </tr>
                          <tr>
                            <td>Maximum Disk Used (/data1) [Gb]</td>
                            <td>%d</td>
                          </tr>
                          <tr>
                            <td>Maximum Memory Utilization [%%]</td>
                            <td>%d</td>
                          </tr>
                          <tr>
                            <td>Maximum CPU Utilization [%%]</td>
                            <td>%d</td>
                          </tr>
                          <tr>
                            <td>Maximum Disk Utilization (/data1) [%%]</td>
                            <td>%d</td>
                          </tr>
                          <tr>
                            <td>EC2 Instance Type</td>
                            <td>%s</td>
                          </tr>
                        </table>
                        </br></br>
                        <table align="center">
                          <tr>
                            <th>Start Time</th>
                            <th>End Time</th>
                            <th>Total Time</th>
                          </tr>
                          <tr>
                            <td>%s</td>
                            <td>%s</td>
                            <td>%s</td>
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
                      var n = data_mem.length;
                      var n_cpu = data_cpu.length;
                      // X scale will use the index of our data
                      var xScale = d3.scaleLinear()
                          .domain([0, n-1]) // input
                          .range([0, width]); // output
                      // X scale for CPU utilization that has interval size of 5 instead of 1
                      var xScale_cpu = d3.scaleLinear()
                          .domain([0, n_cpu-1]) // input
                          .range([0, width]); // output
                      // Y scale will use the randomly generate number
                      var yScale = d3.scaleLinear()
                          .domain([0, 100]) // input
                          .range([height, 0]); // output
                      // d3's line generator
                      var line = d3.line()
                          .x(function(d, i) { return xScale(i); }) // set the x values for the line generator
                          .y(function(d) { return yScale(d.y); }) // set the y values for the line generator
                          //.curve(d3.curveMonotoneX) // apply smoothing to the line
                      // d3's line generator for CPU utilization
                      var line_cpu = d3.line()
                          .x(function(d, i) { return xScale_cpu(i); }) // set the x values for the line generator
                          .y(function(d) { return yScale(d.y); }) // set the y values for the line generator
                          //.curve(d3.curveMonotoneX) // apply smoothing to the line
                      // An array of objects of length N. Each object has key -> value pair, the key being "y" and the value is a random number
                      var dataset_mem = d3.range(n).map(function(d) { return {"y": data_mem[d] } })
                      var dataset_disk = d3.range(n).map(function(d) { return {"y": data_disk[d] } })
                      var dataset_cpu = d3.range(n_cpu).map(function(d) { return {"y": data_cpu[d] } })
                      // Add the SVG to the page
                      var svg = d3.select("#" + div).append("svg")
                          .attr("width", width + margin.left + margin.right)
                          .attr("height", height + margin.top + margin.bottom)
                        .append("g")
                          .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
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
                      var n = data.length;
                      // X scale will use the index of our data
                      var xScale = d3.scaleLinear()
                          .domain([0, n-1]) // input
                          .range([0, width]); // output
                      // Y scale will use the randomly generate number
                      var yScale = d3.scaleLinear()
                          .domain([0, d3.max(data)]) // input
                          .range([height, 0]); // output
                      // d3's line generator
                      var line = d3.line()
                          .x(function(d, i) { return xScale(i); }) // set the x values for the line generator
                          .y(function(d) { return yScale(d.y); }) // set the y values for the line generator
                          //.curve(d3.curveMonotoneX) // apply smoothing to the line
                      // An array of objects of length N. Each object has key -> value pair, the key being "y" and the value is a random number
                      var dataset = d3.range(n).map(function(d) { return {"y": data[d] } })
                      // Add the SVG to the page
                      var svg = d3.select("#" + div).append("svg")
                          .attr("width", width + margin.left + margin.right)
                          .attr("height", height + margin.top + margin.bottom)
                        .append("g")
                          .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
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
                    /* Reading data and Plotting */
                    d3.tsv("metrics.tsv").then(function(data) {
                        return data.map(function(d){
                          if (Number.isNaN(parseFloat(d.max_mem_used_MB)) == false) {
                            return parseFloat(d.max_mem_used_MB);
                          }
                        });
                      }).then(function(d){
                        line_plot(d, 'chart_max_mem', 'Memory used [Mb]');
                    });
                    d3.tsv("metrics.tsv").then(function(data) {
                        return data.map(function(d){
                          if (Number.isNaN(parseFloat(d.min_mem_available_MB)) == false) {
                            return parseFloat(d.min_mem_available_MB);
                          }
                        });
                      }).then(function(d){
                        line_plot(d, 'chart_min_mem', 'Memory available [Mb]');
                    });
                    d3.tsv("metrics.tsv").then(function(data) {
                        return data.map(function(d){
                          if (Number.isNaN(parseFloat(d.max_disk_space_used_GB)) == false) {
                            return parseFloat(d.max_disk_space_used_GB);
                          }
                        });
                      }).then(function(d){
                        line_plot(d, 'chart_disk', 'Disk space used [Gb]');
                    });
                    d3.tsv("metrics.tsv").then(function(data) {
                        var data_array = [[], [], []]
                        data.forEach(function(d) {
                            if (Number.isNaN(parseFloat(d.max_mem_utilization_percent)) == false) {
                              data_array[0].push(parseFloat(d.max_mem_utilization_percent));
                            }
                            if (Number.isNaN(parseFloat(d.max_disk_space_utilization_percent)) == false) {
                              data_array[1].push(parseFloat(d.max_disk_space_utilization_percent));
                            }
                            if (Number.isNaN(parseFloat(d.max_cpu_utilization_percent)) == false) {
                              data_array[2].push(parseFloat(d.max_cpu_utilization_percent));
                            }
                        });
                        return data_array;
                      }).then(function(d_a){
                        percent_plot(d_a, 'chart_percent');
                    });
                    </script>\
                """

            fo.write(html % (self.max_mem_used_MB, self.min_mem_available_MB, self.max_disk_space_used_GB,
                             self.max_mem_utilization_percent, self.max_cpu_utilization_percent, self.max_disk_space_utilization_percent,
                             instance_type,
                             str(self.start), str(self.end), str(self.end - self.start)
                            )
                    )
        return(filename)

    def write_tsv(self, directory, **kwargs): # kwargs, key: (chunks_all_pts, interval), interval is 1 or 5 min
        filename = directory + '/' + 'metrics.tsv'
        with open(filename, 'w') as fo:
            # preparing data and writing header
            data_unpacked = []
            for i, (key, (arg, int)) in enumerate(kwargs.items()):
                if i == 0:
                    fo.write('interval\t' + key)
                else:
                    fo.write('\t' + key)
                tmp = []
                if int == 1:
                    [tmp.extend(a) for a in arg]
                    data_unpacked.append(tmp[:])
                else: # interval is 5
                    [tmp.extend(a) for a in arg]
                    tmp_ext = []
                    [tmp_ext.extend([t, '-', '-', '-', '-']) for t in tmp]
                    data_unpacked.append(tmp_ext[:])
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
            fo.write('End_time' + '\t' + str(self.end) + '\n')
            fo.write('Instance_Type' + '\t' + instance_type + '\n')
        return(filename)
