# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What is Tibanna

Tibanna runs portable genomic pipelines (CWL/WDL/Snakemake/shell) on AWS Cloud. It uses the **Unicorn architecture**: a serverless scheduler built on AWS Step Functions and Lambda that spins up EC2 instances on demand to execute workflow jobs and then terminates them.

## Commands

```bash
# Install dependencies (requires poetry==1.4.2)
make install

# Run tests (requires AWS credentials configured)
make test                        # full test suite via invoke
pytest tests/tibanna/unicorn/    # run unit tests directly
pytest -vv --last-failed         # re-run only failing tests
pytest tests/tibanna/unicorn/test_job.py  # run a single test file

# Lint
make lint   # flake8 tibanna (max line length 120)

# Update dependencies
make update
```

Tests require AWS credentials and access to shared S3 state, so they must run serially (no parallelism in CI). Tests in `tests/tibanna/post_deployment/` are integration tests that require a deployed Tibanna stack.

## Architecture

### Two packages in one repo

- **`tibanna/`** — Python API and CLI (`tibanna` entrypoint). Used by humans and automation to submit jobs and manage the Tibanna deployment.
- **`awsf3/`** — AWS Workflow Framework CLI (`awsf3` entrypoint). Runs *inside* EC2 instances to download inputs, execute the workflow engine, and upload outputs. Not meant for direct user interaction.

### Request flow

1. User calls `tibanna run_workflow` (CLI) or `API().run_workflow()` (Python).
2. `core.py` validates the input, uploads the execution JSON to S3, and starts an AWS Step Function execution.
3. The Step Function invokes the **`run_task_awsem`** Lambda (`lambdas/run_task_awsem.py`), which calls `ec2_utils.py` to launch an EC2 instance with the appropriate AMI and instance type.
4. The EC2 instance runs `awsf3` scripts (`awsf3/aws_run_workflow_generic.sh`) which: decode the run JSON, mount S3 via `mountpoint-s3`, download the workflow definition, run CWL/WDL/Snakemake/shell, then upload outputs and a `postrun.json` back to S3.
5. The Step Function polls via the **`check_task_awsem`** Lambda until the job completes.
6. The **`update_cost_awsem`** Lambda records EC2 cost in DynamoDB.

### Key modules

| Module | Role |
|---|---|
| `tibanna/core.py` | `API` class — all public operations (`run_workflow`, `deploy_unicorn`, `stat`, `log`, `kill`, `rerun`, `cost`, etc.) |
| `tibanna/ec2_utils.py` | `UnicornInput` parsing, EC2 launch logic, instance type selection via Benchmark-4dn |
| `tibanna/awsem.py` | `AwsemRunJson` / `AwsemPostRunJson` — the serialized job spec written to S3 |
| `tibanna/stepfunction.py` | `StepFunctionUnicorn` — Step Function definition and deployment |
| `tibanna/job.py` | `Job` — represents a running or completed workflow execution |
| `tibanna/vars.py` | All environment variables, AWS defaults, AMI mappings, Lambda/SFN name constants |
| `tibanna/utils.py` | S3 helpers, job ID creation, settings management |
| `tibanna/iam_utils.py` | IAM role and user group creation for deployment |
| `tibanna/pricing_utils.py` | EC2 cost calculation and reporting |
| `tibanna/cw_utils.py` | CloudWatch metrics collection |
| `tibanna/__main__.py` | CLI (click-based), delegates everything to `API` |
| `awsf3/utils.py` | Workflow execution inside EC2 — download, run, upload |
| `awsf3/target.py` | Input/output target abstraction (S3 paths) |

### Execution JSON

The central data structure is the execution JSON (`AwsemRunJson`), which describes a single job: input files (S3 URIs), workflow definition, instance requirements, output destinations. The canonical schema is documented in `docs/execution_json.rst`.

### Deployment

`tibanna deploy_unicorn` deploys the three Lambda functions and the Step Function to AWS. Lambda code lives in `tibanna/lambdas/`. The Docker image used for awsf3 inside EC2 is built and published separately via `make publish-docker`.

## Environment variables

Key variables (all with defaults, set via environment or `tibanna/vars.py`):
- `TIBANNA_AWS_REGION` — AWS region (falls back to boto3 session region)
- `AWS_ACCOUNT_NUMBER` — resolved automatically via STS if not set
- `TIBANNA_DEFAULT_STEP_FUNCTION_NAME` — Step Function name for the deployed stack
- `DYNAMODB_TABLE` — DynamoDB table for job tracking

## Testing notes

- Unit tests live in `tests/tibanna/unicorn/` and mock AWS calls.
- CI runs Python 3.8–3.12 sequentially (not in parallel) because tests share S3 state.
- Coverage minimum is 25% (enforced by `--cov-fail-under 25` in pytest config).

## Project agent memory (sharp edges)

Durable project-specific gotchas discovered through real work — add to these as more are found.

### Testing is live-AWS-coupled by default - most tests need real credentials

`invoke test` (the `tasks.py` entry point CI runs) executes the entire `tests/tibanna/` tree with no marker filtering; `@pytest.mark.webtest` is documentation only, not an actual `-m` exclusion. Most existing tests (e.g. `tests/tibanna/unicorn/test_utils.py`, most of `test_ec2_utils.py`) hit real S3/EC2/CloudWatch/Pricing APIs, including read-only Pricing `GetProducts` calls that still require valid signed AWS credentials. `Execution(...)` construction (`tibanna/ec2_utils.py`) always calls `ec2.describe_instance_types` regardless of how instance type is specified.

When writing an offline regression test: mock `<module>.boto3.client` (each module does its own `import boto3`, so patch the one the code under test actually calls from, e.g. `tibanna.ec2_utils.boto3.client`) rather than trying to run the real AWS calls. For `Execution`, mock `describe_instance_types` to return an entry with both `EbsInfo.EbsOptimizedSupport` and `ProcessorInfo.SupportedArchitectures` set, or the constructor raises `KeyError`.

### `import tibanna` hits AWS at import time unless overridden

`tibanna/vars.py` calls `boto3.session.Session().get_credentials()` and (unless `AWS_ACCOUNT_NUMBER`/`TIBANNA_AWS_REGION` env vars are set) `boto3.client('sts').get_caller_identity()` and `Session().region_name` at module import. For any offline work (running tests, a REPL, etc.) without live/valid AWS credentials in the environment, export dummy `AWS_ACCOUNT_NUMBER` and `TIBANNA_AWS_REGION` first to skip the network calls entirely.

### The run_task Lambda does not bundle `awsf3/`

`tibanna/core.py:API.tibanna_packages` (passed as `package_objects` to `aws_lambda.deploy_function` from the `python-lambda-4dn` dependency) `copytree`s only the `tibanna/` package directory into the Lambda zip - `awsf3/` is a sibling directory and is never bundled. Anything the run_task Lambda needs at runtime from the awsf3 bootstrap scripts (e.g. pinned sha256 checksums, see `tibanna/awsf3_checksums.py`) must live as a Python constant inside `tibanna/`, not be read from `awsf3/*` on disk - that path does not exist in the deployed Lambda.

### Env vars must be added to `core.py:env_list` to reach the deployed Lambda

Setting an env var in the deployer's local shell before `tibanna deploy_unicorn`/`deploy_core` has no effect on the running Lambda unless that var is also listed in `API.env_list()` in `tibanna/core.py`, which becomes the Lambda's `Environment.Variables` at deploy time (see `TIBANNA_REPO_BRANCH`, `TIBANNA_AWSF_SCRIPT_VERIFICATION_DISABLED`).

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
