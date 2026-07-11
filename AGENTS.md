# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.

## Testing is live-AWS-coupled by default - most tests need real credentials

`invoke test` (the `tasks.py` entry point CI runs) executes the entire `tests/tibanna/` tree with no marker filtering; `@pytest.mark.webtest` is documentation only, not an actual `-m` exclusion. Most existing tests (e.g. `tests/tibanna/unicorn/test_utils.py`, most of `test_ec2_utils.py`) hit real S3/EC2/CloudWatch/Pricing APIs, including read-only Pricing `GetProducts` calls that still require valid signed AWS credentials. `Execution(...)` construction (`tibanna/ec2_utils.py`) always calls `ec2.describe_instance_types` regardless of how instance type is specified.

When writing an offline regression test: mock `<module>.boto3.client` (each module does its own `import boto3`, so patch the one the code under test actually calls from, e.g. `tibanna.ec2_utils.boto3.client`) rather than trying to run the real AWS calls. For `Execution`, mock `describe_instance_types` to return an entry with both `EbsInfo.EbsOptimizedSupport` and `ProcessorInfo.SupportedArchitectures` set, or the constructor raises `KeyError`.

## `import tibanna` hits AWS at import time unless overridden

`tibanna/vars.py` calls `boto3.session.Session().get_credentials()` and (unless `AWS_ACCOUNT_NUMBER`/`TIBANNA_AWS_REGION` env vars are set) `boto3.client('sts').get_caller_identity()` and `Session().region_name` at module import. For any offline work (running tests, a REPL, etc.) without live/valid AWS credentials in the environment, export dummy `AWS_ACCOUNT_NUMBER` and `TIBANNA_AWS_REGION` first to skip the network calls entirely.

## The run_task Lambda does not bundle `awsf3/`

`tibanna/core.py:API.tibanna_packages` (passed as `package_objects` to `aws_lambda.deploy_function` from the `python-lambda-4dn` dependency) `copytree`s only the `tibanna/` package directory into the Lambda zip - `awsf3/` is a sibling directory and is never bundled. Anything the run_task Lambda needs at runtime from the awsf3 bootstrap scripts (e.g. pinned sha256 checksums, see `tibanna/awsf3_checksums.py`) must live as a Python constant inside `tibanna/`, not be read from `awsf3/*` on disk - that path does not exist in the deployed Lambda.

## Env vars must be added to `core.py:env_list` to reach the deployed Lambda

Setting an env var in the deployer's local shell before `tibanna deploy_unicorn`/`deploy_core` has no effect on the running Lambda unless that var is also listed in `API.env_list()` in `tibanna/core.py`, which becomes the Lambda's `Environment.Variables` at deploy time (see `TIBANNA_REPO_BRANCH`, `TIBANNA_AWSF_SCRIPT_VERIFICATION_DISABLED`).

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
