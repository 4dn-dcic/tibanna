=========================
Monitoring a workflow run
=========================


Monitoring can be done either from the Step Function Console through a Web Browser, or through command-line.



Command-line
------------

General stats
+++++++++++++

::

    invoke stat [--sfn=<stepfunctioname>] [--status=RUNNING|SUCCEEDED|FAILED|TIMED_OUT|ABORTED]

The output is a table (an example below)

::

    jobid       status  name    start_time      stop_time
    2xPih7reR6FM        RUNNING md5        2018-08-15 17:45        2018-08-15 17:50
    3hbkJB3hv92S        SUCCEEDED       hicprocessingbam   2018-08-15 16:04        2018-08-15 16:09
    UlkvH3gbBBA2        FAILED  repliseq-parta     2018-08-09 18:26        2018-08-09 19:01
    j7hvisheBV27        SUCCEEDED       bwa-mem    2018-08-09 18:44        2018-08-09 18:59


Execution logs
++++++++++++++

Using your job ID, you can also check your S3 bucket to see if you can find a file named <jobid>.log. This will happen 5~10min after you start the process, because it takes time for an instance to be ready and send the log file to S3. The log file gets updated, so you can re-download this file and check the progress.

::

    aws s3 cp s3://<tibanna_lob_bucket_name>/<jobid>.log .


Detailed monitoring through ssh
+++++++++++++++++++++++++++++++


You can also ssh into your running instance to check more details. The 'instance_ip' field in the 'input' of 'CheckTaskAwsem' contains the IP.

If your CWL version is draft-3 (AMI is based on Amazon Linux)

::

    ssh ec2-user@<ip>

If your CWL version is v1 (AMI is based on ubuntu)

::

    ssh ubuntu@<ip>


The password is the password you entered as part of the input json (inside 'config' field, in this case, 'whateverpasswordworks') The purpose of the ssh is to monitor things, so refrain from doing various things there, which could interfere with the run. It is recommended, unless you're a developer, to use the log file than ssh.

On the instance, one can check the following, for example.

:/data1/input/:
  - input files

:/data1/tmp*:
  - temp/intermediate files (need sudo access)

:/data1/output/:
  - output files (need sudo access)

:top: 
  - to see what processes are running and how much cpu/memory is being used

:ps -fe:
  - to see what processes are running, in more detail


Console
-------


EC2 instances
+++++++++++++

You can also check from the Console the instance that is running which has a name awsem-<jobid>. It will terminate itself when the run finishes. You won't have access to terminate this or any other instance, but if something is hanging for too long, please contact the admin to resolve the issue.


.. image:: images/awsem_ec2_console.png


Step functions
++++++++++++++


When the run finishes successfully, you'll see in your bucket a file <jobid>.success. If there was an error, you will see a file <jobid>.error instead. The step functions will look green on every step, if the run was successful. If one of the steps is red, it means it failed at that step.


=========================  ======================
        Success                   Fail
=========================  ======================
|unicorn_stepfun_success|  |unicorn_stepfun_fail|
=========================  ======================

.. |unicorn_stepfun_success| image:: images/stepfunction_unicorn_screenshot.png
.. |unicorn_stepfun_fail| image:: images/stepfunction_unicorn_screenshot_fail.png


