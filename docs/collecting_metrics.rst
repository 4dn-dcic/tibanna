============================
Collecting Resources Metrics
============================

Tibanna can collect Cloud Watch metrics on used resources in real time for each run. The metrics are saved as tsv files together with an html report automatically created for visualization.
The metrics are collected by 1 minute interval or 5 minute interval depending on the availability on Cloud Watch. The metrics and html files created are uploaded to an S3 bucket.


plot_metrics
------------
This command allows to save Cloud Watch data collected in the required time interval and creates an html report for the visualization.

By default the command will retrieve the data from cloud watch, and creates several files:

  - a metrics.tsv file containing all the data points
  - a metrics_report.tsv containing the average statistics and other information about the EC2 instance
  - a metrics.html report for visualization

All the files are eventually uploaded to a folder named <jobid>.metrics inside the log S3 bucket specified for tibanna output.
To visualize the html report the URL structure is: ``https://<log-bucket>.s3.amazonaws.com/<jobid>.metrics/metrics.html``

**Basic Command**

::

  tibanna plot_metrics --job-id=<jobid> [<options>]

**Options**

::

  -s|--sfn=<stepfunctionname>         An example step function name may be
                                      'tibanna_unicorn_defaut_3978'. If not specified, default
                                      value is taken from environmental variable
                                      TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                      variable is not set, it uses name 'tibanna_pony' (4dn
                                      default, works only for 4dn).

  -f|--force-upload                   Upload the metrics reports to the S3 bucket even
                                      if there is a lock file (upload is blocked by default
                                      by the lock)

  -u|--update-html-only               Update only the html file for metrics visualization

  -B|--do-not-open-browser            Do not open the browser to visualize the metrics html
                                      after it has been created/updated

When metrics are collected for a run that is complete, a lock file is automatically created inside the same folder. The command will not update the metrics files if a lock file is present. To override this behavior the ``--force-upload`` flag allows to upload the metrics files ignoring the lock.
The ``--update-html-only`` allows to only update the metrics.html file without modifying the other tsv files.
By default the command will open the html report in the browser for visualization when execution is complete, ``--do-not-open-browser`` can be added to prevent this behavior.


Metrics collected
+++++++++++++++++


The metrics that are collected are:

  - EC2 Instance type
----

  - Memory, Disk, and CPU utilization as a percentage of the maximum resources available for the EC2 instance
  - Memory used in Mb
  - Memory available in Mb
  - Disk used in Gb
----

  - Start time, end time, and total elapsed time


html report example
+++++++++++++++++++


.. image:: images/report.png


cost
----

This command allows to retrieve the cost for the run. The cost is not immediately ready and usually requires few days to become available. The command eventually allows to update the information obtained with plot_metrics by adding the cost.

::

 tibanna cost --job-id=<jobid> [<options>]

**Options**

::

 -s|--sfn=<stepfunctionname>         An example step function name may be
                                     'tibanna_unicorn_defaut_3978'. If not specified, default
                                     value is taken from environmental variable
                                     TIBANNA_DEFAULT_STEP_FUNCTION_NAME. If the environmental
                                     variable is not set, it uses name 'tibanna_pony' (4dn
                                     default, works only for 4dn).

 -u|--update-tsv                     Update with the cost the tsv file that stores metrics
                                     information on the S3 bucket
