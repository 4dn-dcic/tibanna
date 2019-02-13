================
News and updates
================

Publication
+++++++++++

- **Oct 11. 2018**  Tibanna paper is out on Biorxiv! https://www.biorxiv.org/content/early/2018/10/11/440974


Version updates
+++++++++++++++

  
  **Feb 13, 2019** The latest version is now 0.5.9_.

    - Wrong requirement of SECRET env is removed from unicorn installation
    - deploy_unicorn without specified buckets also works
    - deploy_unicorn now has `--usergroup` option
    - cloud metric statistics aggregation with runs > 24 hr now fixed
    - `invoke -l` lists all invoke commands
    - `invoke add_user`, `invoke list` and `invoke users` added
    - `log()` function not assuming default step function fixed
    - `invoke log` working only for currently running jobs fixed


  **Feb 4, 2019** The latest version is now 0.5.8_.

    - ``invoke log`` can be used to stream log or postrun json file.
    - postrun json file now contains Cloudwatch metrics for memory/CPU and disk space for all jobs.
    - ``invoke rerun`` has config override options such as ``--instance-type``, ``shutdown-min``, ``ebs-size`` and ``key-name``
      to rerun a job with a different configuration.


  **Jan 16, 2019** The latest version is now 0.5.7_.

    - Spot instance is now supported. To use a spot instance, use ``"spot_instance": true`` in the ``config`` field in the input execution json.

    ::

        "spot_instance": true,
        "spot_duration": 360


  **Dec 21, 2018** The latest version is now 0.5.6_.

    - CloudWatch set up permission error fixed
    - `invoke kill` works with jobid (previously it worked only with execution arn)
    
    ::

        invoke kill --job-id=<jobid> [--sfn=<stepfunctionname>]

    - A more comprehensive monitoring using `invoke stat -v` that prints out instance ID, IP, instance status, ssh key and password.
    - To update an existing Tibanna on AWS, do the following
    
    ::

        invoke setup_tibanna_env --buckets=<bucket1>,<bucket2>,...
        invoke deploy_tibanna --sfn-type=unicorn --usergroup=<usergroup_name>

    e.g.

    ::

        invoke setup_tibanna_env --buckets=leelab-datafiles,leelab-tibanna-log
        invoke deploy_tibanna --sfn-type=unicorn --usergroup=default_3225



  **Dec 14, 2018** The latest version is now 0.5.5_.

    - Now memory, Disk space, CPU utilization are reported to CloudWatch at 1min interval from the Awsem instance.
    - To turn on Cloudwatch Dashboard (a collective visualization for all of the metrics combined),
      add ``"cloudwatch_dashboard" : true`` to ``"config"`` field of the input execution json.
      

  **Dec 14, 2018** The latest version is now 0.5.4_.

    - Problem of EBS mounting with newer instances (e.g. c5, t3, etc) fixed.
    - Now a common AMI is used for `CWL v1`, `CWL draft3` and `WDL` and it is handled by `awsf/aws_run_workflow_generic.sh`

      - To use the new features, redeploy `run_task_awsem` lambda.
      
      ::

        git pull
        invoke deploy_core run_task_awsem --usergroup=<usergroup>  # e.g. usergroup=default_3046



  **Dec 4, 2018** The latest version is now 0.5.3_.

    - For WDL workflow executions, a more comprehensive log named ``<jobid>.debug.tar.gz`` is collected and sent to the log bucket.
    - A file named ``<jobid>.input.json`` is now sent to the log bucket at the start of all Pony executions.
    - Space usage info is added at the end of the log file for WDL executions.
    - ``bigbed`` files are registered to Higlass (pony).
    - Benchmark for ``encode-chipseq`` supported. This includes double-nested array input support for Benchmark.
    - ``quality_metric_chipseq`` and ``quality_metric_atacseq`` created automatically (Pony).
    - An empty extra file array can be handled now (Pony).
    - When Benchmark fails, now Tibanna returns which file is missing.


  **Nov 20, 2018** The latest version is now 0.5.2_.

    - User permission error for setting postrun jsons public fixed
    - ``--no-randomize`` option for ``invoke setup_tibanna_env`` command to turn off adding random number
      at the end of usergroup name.
    - Throttling error upon mass file upload for md5/fastqc trigger fixed.


  **Nov 19, 2018** The latest version is now 0.5.1_.

    - Conditional alternative outputs can be assigned to a global output name (useful for WDL)


  **Nov 8, 2018** The latest version is now 0.5.0_.

    - WDL and Double-nested input array is now also supported for Pony.


  **Nov 7, 2018** The latest version is now 0.4.9_.

    - Files can be renamed upon downloading from s3 to an ec2 instance where a workflow will be executed.


  **Oct 26, 2018** The latest version is now 0.4.8_.

    - Double-nested input file array is now supported for both CWL and WDL.


  **Oct 24, 2018** The latest version is now 0.4.7_.

    - Nested input file array is now supported for both CWL and WDL.

 
  **Oct 22, 2018** The latest version is now 0.4.6_.

    - Basic *WDL* support is implemented for Tibanna Unicorn!
 

  **Oct 11. 2018** The latest version is now 0.4.5_.

    - Killer CLIs ``invoke kill`` is available to kill specific jobs and ``invoke kill_all`` is available to kill all jobs. They terminate both the step function execution and the EC2 instances.


.. _0.5.9: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.9
.. _0.5.8: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.8
.. _0.5.7: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.7
.. _0.5.6: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.6
.. _0.5.5: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.5
.. _0.5.4: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.4
.. _0.5.3: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.3
.. _0.5.2: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.2
.. _0.5.1: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.1
.. _0.5.0: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.0
.. _0.4.9: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.9
.. _0.4.8: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.8
.. _0.4.7: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.7
.. _0.4.6: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.6
.. _0.4.5: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.5

