
==========
Change Log
==========

6.0.0
=====

* Replace Goofys with mountpoint-s3 (https://github.com/awslabs/mountpoint-s3)
* Security - S3 objects (metrics, cost, marker, run and postrun files) uploaded by
  Tibanna are now private by default; public output requires an explicit per-call
  opt-in. ``deploy_unicorn``/``setup_tibanna_env`` now retain S3 Block Public Access
  on the given buckets by default; pass the new ``-Q/--enable-public-access-block-deletion``
  flag (``do_not_delete_public_access_block=False`` in the API) to restore the old
  behavior for an approved public-output deployment. This code change does not
  revoke ACLs already applied to existing objects/buckets - operators who deployed
  a prior Tibanna version with the old defaults should audit and, if needed,
  explicitly remediate any previously-public buckets/objects.
* Fix workflow finalization being coupled to optional metrics/plotting/cost-estimate
  generation: a completed job with a valid ``.success`` marker and postrun data now
  always finalizes and terminates its instance, even if CloudWatch/plotting/cost
  estimation fails; the failure is recorded as a structured ``Metrics_status``/
  ``Metrics_error`` on the postrun job instead of failing the whole execution.
* Security - reduce IAM blast radius: the run_task Lambda role no longer carries
  the AWS-managed ``AmazonEC2FullAccess`` policy; it now gets a scoped custom
  policy covering only the EC2 actions Tibanna actually calls (RunInstances,
  CreateFleet, CreateLaunchTemplate, DeleteLaunchTemplate, DeleteFleets,
  CreateTags, DescribeInstances, DescribeInstanceTypes). ``ec2:TerminateInstances``
  is now conditioned on the ``Type=awsem`` tag Tibanna applies to instances it
  launches. The step-function role uses the scoped ``lambdainvoke`` policy
  (restricted to the three tibanna lambdas) instead of the managed
  ``AWSLambdaRole`` policy, which granted ``lambda:InvokeFunction`` on
  ``Resource: "*"``. Existing deployments must redeploy
  (``tibanna deploy_unicorn``/``setup_tibanna_env``) to pick up the new,
  narrower policies.
* Security - worker instances no longer fetch their bootstrap/monitoring scripts
  from the mutable ``master`` branch by default: ``TIBANNA_REPO_BRANCH`` now
  defaults to this package's own immutable release tag (``v`` + version,
  matching the existing ``DEFAULT_AWSF_IMAGE`` convention), and the downloaded
  ``aws_run_workflow_generic.sh``,
  ``cloudwatch_agent_config.json`` and ``spot_failure_detection.sh`` are each
  verified against a pinned sha256 (``tibanna/awsf3_checksums.py``) before
  being executed/used - a mismatch or unavailable download fails closed
  (stops before mounting disks or running Docker/workload code) rather than
  running unverified code. A development-only override,
  ``TIBANNA_AWSF_SCRIPT_VERIFICATION_DISABLED=true``, is available for a
  custom ``TIBANNA_REPO_BRANCH`` fork whose scripts are not tracked in
  ``awsf3_checksums.py`` - never set this in a real deployment. Also fixes:
  a fatal host-bootstrap error (missing log bucket/version/image, EBS
  mount/format failure, Docker pull exhaustion, Docker run failure) now
  fails closed (exits immediately after reporting the error) instead of
  merely scheduling a delayed shutdown and continuing into subsequent setup
  and workload execution.
* Fix several low-risk correctness defects: ``rerun_many`` now paginates
  ``list_executions`` instead of silently processing only the first page, and
  no longer raises a ``TypeError`` from comparing a naive/aware datetime in its
  ``stopDate`` filter; ``list_sfns``' ``-s/--sfn-type`` flag is now actually
  passed through instead of being ignored; ``rerun_many``'s ``-o/--offset``
  is now parsed as an int so it no longer crashes when added to ``stophour``;
  cost estimates and ``top`` metric timelines now use ``timedelta.total_seconds()``
  instead of ``.seconds`` so they are correct for jobs spanning more than a day.


5.5.3
=====

* Increase timeout limit for lambda functions


5.5.2
=====
* Security - refactor Tibanna to use IMDSv2


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
