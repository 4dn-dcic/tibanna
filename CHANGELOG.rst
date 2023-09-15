
==========
Change Log
==========

4.0.0
=====

* Drop support for 3.7
* Support 3.9, 3.10


3.3.3
=====

* Remove unused `requests` dependency

3.3.2
=====

* Add ``instance_start_time`` to ``tibanna stat`` command


3.3.1
=====
`PR 390: Bump Benchmark <https://github.com/4dn-dcic/tibanna/pull/390>`_

* Bump Benchmark


3.3.0
=====
`PR 388: Improved fleet error handling + smaller fixes <https://github.com/4dn-dcic/tibanna/pull/388>`_

* Improved fleet error handling + smaller fixes


3.2.2
=====
`PR 387: Add kwargs <https://github.com/4dn-dcic/tibanna/pull/387>`_

* Add kwargs to various class' init methods


3.2.1
=====

* Fix issue where costs could be inflated when running spot


3.1.0 - yanked (do not use)
=====

* Add config option ``ami_per_region``.
* Bump ``cwltool`` version to ``3.1.20211103193132``.
* Singularity was not working. Also, bump Singularity version to ``3.10.4``.
* Speed up Tibanna docker build.
* Fix Goofys installation on ARM architecture.


3.0.1  - yanked (do not use)
=====

* Add CodeBuild specification.


3.0.0 - yanked (do not use)
=====

* Added support for Graviton instances. 
* Removed ``other_instance_types`` as option for ``behavior_on_capacity_limit``. It will fall back to ``wait_and_retry``.
* Multiple instance types can be specified in the configuration. If ``spot_instance`` is enabled, Tibanna will run the workflow on the instance with the highest available capacity. If ``spot_instance`` is disabled, it will run the workflow on the cheapest instance in the list.
* Instead of using the ``run_instance`` command we switch to EC2 fleets (in instant mode) to start up instances. 


2.2.6
=====

* Fixed bug where Tibanna would use and report and incorrect overall CPU utilization of the EC2 instance.
