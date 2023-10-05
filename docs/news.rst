================
News and updates
================

Publication
+++++++++++

- **May 15, 2019**  Tibanna paper is out on Bioinformatics now! https://doi.org/10.1093/bioinformatics/btz379 
- **Apr 18. 2019**  A newer version of the Tibanna paper is out on Biorxiv! https://www.biorxiv.org/content/10.1101/440974v3
- **Oct 11. 2018**  Tibanna paper preprint is out on Biorxiv! https://www.biorxiv.org/content/early/2018/10/11/440974


Version updates
+++++++++++++++


  For more recent version updates, check out Tibanna releases_


.. _releases: https://pypi.org/project/tibanna/

  **Sep 15, 2023** The latest version is now 4.0.0_.
    - Support for Python 3.7 has been dropped
    - Added support for Python 3.9 and 3.10
    - Added support for Python 3.11

  **Nov 18, 2022** The latest version is now 3.0.0_.
    - Tibanna now supports AWS Graviton-based instances.
    - The instance type configuration now allows single instances (e.g., ``t3.micro``) and lists (e.g., ``[t3.micro, t3.small]``). If ``spot_instance`` is enabled, Tibanna will run the workflow on the instance with the highest available capacity. If ``spot_instance`` is disabled, it will run the workflow on the cheapest instance in the list.
    - The option ``other_instance_types`` for ``behavior_on_capacity_limit`` has been removed. It will fall back to ``wait_and_retry``.


  **Mar 10, 2022** The latest version is now 2.0.0_.
    - The default Python version for Tibanna is now 3.8 (or 3.7). Python 3.6 is no longer supported.


  **Sep 16, 2019** The latest version is now 0.9.1_.

    - A new functionality of generating a resource metrics report html is now added! This report includes a graph of CPU/Memory/disk space utilization and usage at 1min interval, as well as a table of summary metrics.
      - After each run, an html report gets automatically added to the ``log_bucket`` which can be viewed using a Web Browser. However, for this to take effect, the unicorn must be redeployed.
      - The new ``plot_metrics`` function of CLI (``tibanna plot_metrics -h``) allows users to create the resource metrics report before a run it complete.
      - The same function can be used through Python API (``API().plot_metrics(job_id=<jobid>, ...)``)
    - A new functionality ``cost`` is added to the tibanna CLI/API, to retrieve the cost of a specific run.
      - ``tibanna cost --job-id=<jobid>``
      - It usually takes a day for the cost to be available.
      - The cost can also be added to the resource plot, by

      ::

          tibanna cost -j <jobid> --update-tsv
          tibanna plot_metrics -j <jobid> --update-html-only --force-upload
    
      - A new dynamoDB-based jobID indexing is enabled! This allows users to search by jobid without specifying step function name and even after the execution expires (e.g. ``tibanna log``, ``tibanna plot_metrics``)
        - To use this feature, the unicorn must be redeployed. Only the runs created after the redeployment would be searchable using this feature. When the jobid index is not available, tibanna automatically switches to the old way of searching.
        - DynamoDB may add to the cost but very minimally (up to $0.01 per month in case of 4DN)
      - ``Benchmark`` ``0.5.5`` is used now for 4DN pipelines.
      - ``run_workflow`` now has ``--do-not-open-browser`` option that disables opening the Step function execution on a Web Browser.


  **Aug 14, 2019** The latest version is now 0.9.0_.

    - ``root_ebs_size`` now supported (default 8) as a config field.
      (useful for large docker images or multiple docker images, which uses root EBS)
    - ``TIBANNA_AWS_REGION`` and ``AWS_ACCOUNT_NUMBER`` no longer required as environment variables.


  **Jul 22, 2019** The latest version is now 0.8.8_.

    - Fixed installation issue caused by ``python-lambda-4dn``
    - Input file can now be a directory for ``shell`` and ``snakemake``
      - e.g. ``"file:///data1/shell/somedir" : "s3://bucketname/dirname"``
    - Output target can now be a directory for ``shell`` and ``snakemake``
      - e.g. ``"file:///data1/shell/somedir": "dirname"``


  **Jul 8, 2019** The latest version is now 0.8.7_.

    - ec2 termination policy is added to usergroup to support ``kill`` function
    - ``run_workflow`` ``verbose`` option is now passed to ``dynamodb``


  **Jun 25, 2019** The latest version is now 0.8.6_.

    - A newly introduced issue of not reporting ``Metric`` after the run is now fixed.
    - With ``tibanna log``, when the log/postrunjson file is not available, it does not raise an error but prints a message.
    - Benchmark ``0.5.4`` is used instead of ``0.5.3`` for 4DN pipelines.


  **Jun 14, 2019** The latest version is now 0.8.5_.

    - A newly introduced bug in the ``rerun`` cli (not working) now fixed.


  **Jun 12, 2019** The latest version is now 0.8.4_.

    - The issue of auto-determined EBS size being sometimes not an integer fixed.
    - Now input files in the unicorn input json can be written in the format of ``s3://bucket/key`` as well as ``{'bucket_name': bucket, 'object_key': key}``
    - command can be written in the format of a list for aesthetic purpose (e.g. ``[command1, command2, command3]`` is equivalent to ``command1; command2; command3``)


  **Jun 10, 2019** The latest version is now 0.8.3_.

    - A newly introduced issue of ``--usergroup`` not working properly with ``deploy_unicorn``/``deploy_core`` is now fixed.
    - Now one can specify ``mem`` (in GB) and ``cpu`` instead of ``instance_type``. The most cost-effective instance type will be auto-determined.
    - Now one can set ``behavior_on_capacity_limit`` to ``other_instance_types``, in which case tibanna will try the top 10 instance types in the order of decreasing hourly cost.
    - EBS size can be specified in the format of ``3x``, ``5.5x``, etc. to make it 3 (or 5.5) times the total input size.


  **Jun 3, 2019** The latest version is now 0.8.2_.

    - One can now directly send in a command and a container image without any CWL/WDL (language = ``shell``).
    - One can now send a local/remote(http or s3) Snakemake workflow file to awsem and run it (either the whole thing, a step or multiple steps in it). (language = ``snakemake``)
    - Output target and input file dictionary keys can now be a file name instead of an argument name (must start with ``file://``)
      - input file dictionary keys must be ``/data1/input``, ``/data1/out`` or either ``/data1/shell`` or ``/data1/snakemake`` (depending on the language option).
    - With shell / snakemake option, one can also ``exec`` into the running docker container after sshing into the EC2 instance.
    - The ``dependency`` field can be in args, config or outside both in the input json.


  **May 30, 2019** The latest version is now 0.8.1_.

    - ``deploy_core`` (and ``deploy_unicorn``) not working in a non-venv environment fixed
    - local CWL/WDL files and CWL/WDL files on S3 are supported.
    - new issue with opening the browser with ``run_workflow`` fixed


  **May 29, 2019** The latest version is now 0.8.0_.

    - Tibanna can now be installed via ``pip install tibanna``! (no need to ``git clone``)
    - Tibanna now has its own CLI! Instead of ``invoke run_workflow``, one should use ``tibanna run_workflow``.
    - Tibanna's API now has its own class! Instead of ``from core.utils import run_workflow``, one should use the following.

      ::

          from tibanna.core import API
          API().run_workflow(...)


    - The API ``run_workflow()`` can now directly take an input json file as well as an input dictionary (both through ```input_json`` parameter).
    - The ``rerun`` CLI now has ``--appname_filter`` option exposed
    - The ``rerun_many`` CLI now has ``--appname-filter``, ``--shutdown-min``, ``--ebs-size``, ``--ebs-type``, ``--ebs-iops``, ``--key-name``, ``--name`` options exposed.
      The API also now has corresponding parameters.
    - The ``stat`` CLI now has API and both has a new parameter `n` (`-n`) that prints out the first n lines only. The option ``-v`` (``--verbose``) is not replaced by ``-l`` (``--long``)


  **May 15, 2019** The latest version is now 0.7.0_.

    - Now works with **Python3.6** (2.7 is deprecated!)
    - newly introduced issue with non-list secondary output target handling fixed
    - fixed the issue with top command reporting from ec2 not working any more
    - now the `run_workflow` function does not later the original input dictionary
    - auto-terminates instance when CPU utilization is zero (inactivity) for an hour (mostly due to aws-related issue but could be others).
    - The `rerun` function with a run name that contains a uuid at the end(to differentiate identical run names) now removes it from run_name before adding another uuid.

  **Mar 7, 2019** The latest version is now 0.6.1_.

    - Default **public bucket access is deprecated** now, since it also allows access to all buckets in one's own account.
      The users must specify buckets at deployment, even for public buckets.
      If the user doesn't specify any bucket, the deployed Tibanna will only have access to the public tibanna test buckets of the 4dn AWS account.
    - A newly introduced issue of ``rerun`` with no ``run_name`` in ``config`` fixed.

  
  **Feb 25, 2019** The latest version is now 0.6.0_.

    - The input json can now be simplified.

      - ``app_name``, ``app_version``, ``input_parameters``, ``secondary_output_target``, ``secondary_files`` fields can now be omitted (now optional)
      - ``instance_type``, ``ebs_size``, ``EBS_optimized`` can be omitted if benchmark is provided (``app_name`` is a required field to use benchmark)
      - ``ebs_type``, ``ebs_iops``, ``shutdown_min`` can be omitted if using default ('gp2', '', 'now', respectively)
      - ``password`` and ``key_name`` can be omitted if user doesn't care to ssh into running/failed instances

    - issue with rerun with a short run name containing uuid now fixed.

  **Feb 13, 2019** The latest version is now 0.5.9_.

    - Wrong requirement of ``SECRET`` env is removed from unicorn installation
    - deploy_unicorn without specified buckets also works
    - deploy_unicorn now has ``--usergroup`` option
    - cloud metric statistics aggregation with runs > 24 hr now fixed
    - ``invoke -l`` lists all invoke commands
    - ``invoke add_user``, ``invoke list`` and ``invoke users`` added
    - ``log()`` function not assuming default step function fixed
    - ``invoke log`` working only for currently running jobs fixed


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


.. _2.0.0: https://github.com/4dn-dcic/tibanna/releases/tag/v2.0.0
.. _0.9.1: https://github.com/4dn-dcic/tibanna/releases/tag/v0.9.1
.. _0.9.0: https://github.com/4dn-dcic/tibanna/releases/tag/v0.9.0
.. _0.8.8: https://github.com/4dn-dcic/tibanna/releases/tag/v0.8.8
.. _0.8.7: https://github.com/4dn-dcic/tibanna/releases/tag/v0.8.7
.. _0.8.6: https://github.com/4dn-dcic/tibanna/releases/tag/v0.8.6
.. _0.8.5: https://github.com/4dn-dcic/tibanna/releases/tag/v0.8.5
.. _0.8.4: https://github.com/4dn-dcic/tibanna/releases/tag/v0.8.4
.. _0.8.3: https://github.com/4dn-dcic/tibanna/releases/tag/v0.8.3
.. _0.8.2: https://github.com/4dn-dcic/tibanna/releases/tag/v0.8.2
.. _0.8.1: https://github.com/4dn-dcic/tibanna/releases/tag/v0.8.1
.. _0.8.0: https://github.com/4dn-dcic/tibanna/releases/tag/v0.8.0
.. _0.7.0: https://github.com/4dn-dcic/tibanna/releases/tag/v0.7.0
.. _0.6.1: https://github.com/4dn-dcic/tibanna/releases/tag/v0.6.1
.. _0.6.0: https://github.com/4dn-dcic/tibanna/releases/tag/v0.6.0
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

