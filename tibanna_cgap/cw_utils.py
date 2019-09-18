import boto3, os
from tibanna.utils import (
    printlog,
    upload,
    read_s3
)
# from datetime import timezone
from datetime import datetime
from datetime import timedelta
from tibanna.TibannaResource import TibannaResource_

# instance_id = 'i-0167a6c2d25ce5822'
# filesystem = "/dev/xvdb"
# filesystem = "/dev/nvme1n1"


class TibannaResource(TibannaResource):
    def create_html():
        html = """\
                <!DOCTYPE html>
                <meta charset="utf-8">
                <link href="https://fonts.googleapis.com/css?family=Source+Sans+Pro:200,300,400,600,700,900,300i,400i,600i" rel="stylesheet"/>
                <style type="text/css">
                :root { font-size: 16px }
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
                      <h1>Pipeline Run Metrics</h1>
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
                  // X scale for CPU utilization that has interval size of 5 instead of 1
                  var xScale_cpu = d3.scaleLinear()
                      .domain([0, n_cpu]) // input
                      .range([0, width*(n_cpu)*5/(n)]); // output
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
        return(html)
