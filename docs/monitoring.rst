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
    2xPih7reR6FM        RUNNING md5_f6cf887b-fbd4-4d28-bc65-a31fbd114259        2018-08-15 17:45        2018-08-15 17:50
    3hbkJB3hv92S        SUCCEEDED       hicprocessingbam_553a5376-0f24-4067-8eba-19d2c75751a6   2018-08-15 16:04        2018-08-15 16:09
    UlkvH3gbBBA2        FAILED  repliseq-parta_2336e60a-4fce-420a-9d03-2f31a2a80cc2     2018-08-09 18:26        2018-08-09 19:01
    j7hvisheBV27        SUCCEEDED       bwa-mem_7b0f737e-172d-447b-ba36-0a52bee8fb52    2018-08-09 18:44        2018-08-09 18:59


Execution logs
++++++++++++++

Using your job ID, you can also check your S3 bucket to see if you can find a file named <jobid>.log. This will happen 5~10min after you start the process, because it takes time for an instance to be ready and send the log file to S3. The log file gets updated, so you can re-download this file and check the progress.

::

    aws s3 cp s3://suwang/<jobid>.log .


Advanced monitoring through ssh
+++++++++++++++++++++++++++++++


You can also ssh into your running instance. The 'instance_ip' field in the 'input' of 'CheckTaskAwsem' contains the IP.

::

    ssh ec2-user@<ip>  # if your CWL version is draft-3 (AMI is based on Amazon Linux)

    ssh ubuntu@<ip>  # if your CWL version is v1 (AMI is based on ubuntu)


The password is the password you entered as part of the input json (inside 'config' field, in this case, 'whateverpasswordworks') The purpose of the ssh is to monitor things, so refrain from doing various things there, which could interfere with the run. It is recommended, unless you're a developer, to use the log file than ssh.


Console
-------


EC2 instances
+++++++++++++

You can also check from the Console the instance that is running which has a name awsem-<jobid>. It will terminate itself when the run finishes. You won't have access to terminate this or any other instance, but if something is hanging for too long, please contact the admin to resolve the issue.


|awsem_ec2_console|

.. |awsem_ec2_console| image:: images/awsem_ec2_console.png


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


