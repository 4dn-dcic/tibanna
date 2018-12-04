================
News and updates
================

Publication
+++++++++++

- **Oct 11. 2018**  Tibanna paper is out on Biorxiv! https://www.biorxiv.org/content/early/2018/10/11/440974


Version updates
+++++++++++++++

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


.. _0.5.3: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.3
.. _0.5.2: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.2
.. _0.5.1: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.1
.. _0.5.0: https://github.com/4dn-dcic/tibanna/releases/tag/v0.5.0
.. _0.4.9: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.9
.. _0.4.8: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.8
.. _0.4.7: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.7
.. _0.4.6: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.6
.. _0.4.5: https://github.com/4dn-dcic/tibanna/releases/tag/v0.4.5

