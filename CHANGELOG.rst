
==========
Change Log
==========

5.5.1
=====

* Update dependencies (especially Benchmark)


5.5.0
=====

* Update dependencies (especially Benchmark)


5.4.3
=====

* Fix bug when parsing output from top command


5.4.2
=====

* Safeguard against unexpected output from top command


5.4.1
=====

* Disable idle instance check when `disable_metrics_collection` is active
* Switch to timezone aware datetime object everywhere. In particular, replace deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)`.
* Update docs


5.4.0
=====

* Support for Python 3.12.


5.3.0
=====

* Add config option `disable_metrics_collection`


5.2.2
=====

* Fix docker version in awsf3 Dockerfile


5.2.1
=====

* Update dependencies


5.2.0
=====

* Fix CLI for Python 3.11


5.1.0
=====
* Fixed GA publish which was not working because it could not find dcicutils because
  it is not a dependency in pyproject.toml; workaround is to call it manually via straight
  python and not via pyproject.toml script. N.B. HOWEVER: It still does not work because
  pypi project credentials are not yet defined for this repo.
* Added Python 3.8, 3.9, 3.10, as well as 3.11 for GA CI build. This causes failures
  because of the way the tests were written - writing/reading to/from fixed location in S3,
  which means that concurrent runs do not reliably succeed, i.e. because they are stomping
  on each other. Workaround was to define separate build steps (cloned for now) in main.yml
  with appropriate "needs" clauses which forces them to execute serially.


5.0.0
=====

* Update to Python 3.11.
* Note 3: As of Tibanna version 5.0.0, Python 3.7 (and lower) is no longer supported.
  Please switch to Python 3.11!


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
