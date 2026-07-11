"""SHA-256 checksums of the awsf3 bootstrap/monitoring assets that worker
instances download at launch (D1: worker bootstrap immutability).

These are pinned constants rather than computed at runtime, because the
awsf3/ directory is not bundled into the run_task Lambda deployment package
(only the tibanna/ package is - see core.py:API.tibanna_packages, which is
passed as `package_objects` to aws_lambda.deploy_function and copytree'd
verbatim). The Lambda therefore cannot read awsf3/*.sh from its own local
filesystem to compute a hash at userdata-generation time.

tests/tibanna/unicorn/test_awsf3_checksums.py recomputes these from the
checked-out awsf3/ files and fails if they drift, so a source change to any
of these three files always requires a matching update here.
"""

AWS_RUN_WORKFLOW_GENERIC_SHA256 = 'd3859fb36f98b1ec67cde5f2c31666e470aebfa5fd95a6044d41878724f14bca'
CLOUDWATCH_AGENT_CONFIG_SHA256 = '4c67d8d9da35a98663c6451894d391aa115ace9b85d44674779b1613f0602e14'
SPOT_FAILURE_DETECTION_SHA256 = '6808d9b0320c9da6aefcc0dd5010210da9cc5d447e7d7b2caf9125d13760a883'
