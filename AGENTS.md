# Tibanna agent guide

This is the durable repository memory for agents working on Tibanna. Keep it focused on architecture, workflows, and sharp edges that are costly to rediscover. Prefer links to authoritative code or docs over duplicating implementation details.

## What this repository is

Tibanna runs CWL, WDL, Snakemake, and shell workflows on AWS. The Python package and CLI deploy an AWS Step Functions/Lambda control plane ("Unicorn"), provision one EC2 worker ("AWSEM") per job, and use S3 objects as the durable handoff/status protocol. The worker runs the selected workflow engine in the `tibanna-awsf` container and publishes logs, status markers, post-run metadata, and optional metrics back to S3.

Authoritative overviews are [README.md](README.md), [docs/how_it_works.rst](docs/how_it_works.rst), [docs/execution_json.rst](docs/execution_json.rst), and [docs/installation.rst](docs/installation.rst).

## Repository map

- `tibanna/`: control-plane package. `core.py` is the public API/deployment facade; `__main__.py` defines the CLI; `vars.py` holds environment-derived constants and AWS naming; `stepfunction*.py` define state machines; `run_task.py`/`check_task.py`/`update_cost.py` implement Lambda behavior; `ec2_utils.py` parses jobs and creates launch templates/fleets; `iam_utils.py` provisions roles and policies; `job.py` and `dd_utils.py` map jobs through DynamoDB; `awsem.py` models run/postrun metadata; `cw_utils.py`, `top.py`, and `pricing_utils.py` build metrics and cost reports.
- `tibanna/lambdas/`: deployable Lambda entry modules and Lambda-specific requirements. These thin handlers call the implementation modules above.
- `awsf3/`: current worker-side Python package plus the host bootstrap and spot-monitoring scripts. It decodes the run JSON, stages inputs, runs CWL/WDL/Snakemake/shell workloads, uploads outputs, and emits postrun/status artifacts.
- `awsf3-docker/`: Docker build context for the `tibanna-awsf` worker image. `run.sh` invokes the packaged `awsf3` CLI.
- `awsf/`: legacy worker implementation retained for compatibility; new work normally belongs in `awsf3/`.
- `tests/tibanna/`: control-plane tests, including `unicorn/` and credentialed `post_deployment/` suites. `tests/awsf3/` covers the current worker package and bootstrap shell. `tests/awsf/` covers legacy behavior. `tests/files/` and `test_json/` contain fixtures.
- `examples/`: small CWL/WDL examples and expected files. `docs/`: Sphinx documentation. `old/`: obsolete AMI tooling; do not treat it as the current deployment path.
- `pyproject.toml`/`poetry.lock`: package metadata and locked dependencies. `Makefile` and `tasks.py`: local/CI commands. `.github/workflows/`: CI, tagged PyPI publishing, and manual Read the Docs triggering. `buildspec*.yml`: multi-architecture ECR image builds.

## Orchestration and data flow

1. `tibanna run_workflow` dispatches to `API.run_workflow` in `tibanna/core.py`. It loads the job JSON (`args` describes the workflow/data; `config` describes AWS resources), assigns the job/execution names, uploads local workflow files when needed, starts the main Step Functions execution, optionally starts the cost-updater state machine, and records lookup metadata in the `tibanna-master` DynamoDB table.
2. `StepFunctionUnicorn` in `tibanna/stepfunction.py` builds a two-state loop. `RunTaskAwsem` invokes the run-task Lambda once; `CheckTaskAwsem` polls until a terminal marker is observed. Retryable exceptions are part of the state-machine protocol, so changing exception names or retry lists changes orchestration semantics.
3. `run_task.py` creates `ec2_utils.Execution`. Prelaunch writes `<jobid>.run.json` to the configured log bucket. Launch creates an EC2 launch template and one-instance instant fleet, then returns the instance ID and launch metadata to Step Functions.
4. EC2 user data downloads and verifies `awsf3/aws_run_workflow_generic.sh`, which mounts/formats the data EBS volume, installs monitoring, pulls the versioned worker image, and runs `awsf3-docker/run.sh`. Fatal bootstrap failures must exit immediately and attempt a durable `<jobid>.error` marker; never let setup continue after `handle_error`.
5. The worker reads the run JSON, stages inputs, runs the workflow engine, uploads outputs/logs/postrun JSON, and writes `<jobid>.job_started`, `.success`, `.error`, or `.aborted` S3 markers. These object names and their ordering are an API between the host, Lambdas, CLI, and state machine.
6. `CheckTask.run` in `tibanna/check_task.py` treats those markers as authoritative, finalizes postrun metadata, terminates/reconciles the EC2 instance, and returns or raises the state-machine exception. Final metrics/plot generation is best-effort: a valid success marker and postrun record must remain successful if CloudWatch, pricing, plotting, local report generation, or metrics upload fails.
7. `TibannaResource`/`Top`/`pricing_utils` generate metrics and cost artifacts. The optional cost-updater state machine revisits cost after the primary execution completes.

## Configuration and AWS naming

- `tibanna/vars.py` is the source of truth for environment variables, default names, AMIs, ARNs, timestamp format, and the default worker image. It executes AWS credential/account/region discovery at import time.
- The main deployment commands are `tibanna setup_tibanna_env`, `tibanna deploy_core`, and `tibanna deploy_unicorn`; see `docs/installation.rst` and `docs/commands.rst`. `API.deploy_unicorn` creates/updates IAM, Lambdas, Step Functions, and the optional cost updater. Suffix/usergroup handling must stay consistent across Lambda names, state-machine names, IAM resources, and ARNs.
- Lambda deployment uses `python-lambda-4dn`. `API.env_list()` in `core.py` is the explicit bridge from the deployer's environment to Lambda `Environment.Variables`; merely exporting a variable locally does not propagate it.
- `config.log_bucket` is the control-plane artifact bucket. Workflow input/output buckets must be included in deployment IAM access. `S3_ENCRYPT_KEY_ID` enables KMS use and requires matching S3 permissions, IAM role permissions, and KMS key-policy principals.
- VPC deployment accepts subnets/security groups and passes them both as Lambda VPC configuration and environment values consumed by EC2 selection.
- Defaults and schemas are implemented in `ec2_utils.UnicornInput`, `Args`, and `Config`; user-facing field documentation is in `docs/execution_json.rst`. Preserve old field names and CLI flags unless an explicit migration is part of the task.

## Security and deployment sharp edges

### S3 privacy

`tibanna.utils.upload` and `put_object_s3` are private by default. Public access requires explicit `public=True`; postrun publication is controlled by `config.public_postrun_json`. Bucket-level Block Public Access is retained by default. Deleting it is an explicit opt-in (`--enable-public-access-block-deletion`) and does not repair or revoke ACLs on existing objects. Never make logs, run JSON, metrics, `top` command lines, markers, or locks public implicitly.

### IAM scope

Policy construction lives in `tibanna/iam_utils.py`. The run-task Lambda uses the custom EC2 launch allowlist, not `AmazonEC2FullAccess`; the Step Functions role invokes only Tibanna Lambda ARNs. Termination is conditioned on `ec2:ResourceTag/Type=awsem`, so `ec2_utils.create_launch_template()` must retain the `Type=awsem` instance tag. Lambda ARNs use `:function:` (not `:function/`). When adding an AWS API call, update and test the owning role's policy rather than broadening unrelated roles.

### Bootstrap trust boundary

Worker host bootstrap runs as root. `TIBANNA_REPO_BRANCH` defaults to the release tag matching `tibanna._version.__version__`; tagged releases must contain the exact worker assets whose SHA-256 values are pinned in `tibanna/awsf3_checksums.py`. Source/pre-release deployments before that tag exists must set an explicit immutable ref. `TIBANNA_AWSF_SCRIPT_VERIFICATION_DISABLED=true` is a development-only escape hatch and must not become a production default.

The run-task Lambda packages only `tibanna/` (`API.tibanna_packages`); sibling `awsf3/` files are not present in the Lambda zip. Expected digests therefore live as constants in `tibanna/awsf3_checksums.py`. Any change to `aws_run_workflow_generic.sh`, `cloudwatch_agent_config.json`, or `spot_failure_detection.sh` must update the matching digest and pass the drift test in `tests/tibanna/unicorn/test_ec2_utils_bootstrap_verification.py`.

### Credentials and secrets

Prefer instance/Lambda roles. Optional profile credentials and SSH passwords can reach EC2 user data/process arguments; avoid expanding this legacy path and never log generated user data containing secrets. IMDSv2 is required by the launch template. KMS, S3, and IAM changes must be tested together because a deployment can succeed while the worker lacks runtime access.

### AWS lifecycle behavior

Tests cannot prove EC2 Fleet precedence rules; changes to spot/on-demand fallback need request-shape unit tests plus a gated AWS contract test. Launch templates, fleets, instances, dashboards, Step Functions, Lambdas, roles, policies, instance profiles, DynamoDB records, and S3 artifacts have independent cleanup paths. Do not hide failures that can leave billable/untracked compute. Do not run deploy/cleanup/live AWS mutation as part of ordinary local validation.

## Local development and tests

Supported Python versions are 3.8 through 3.12. CI installs Poetry 1.4.2 and runs Python versions serially because tests share fixed AWS/S3 resources.

Common commands:

```bash
make install                         # poetry install
make lint                            # flake8 tibanna
make test                            # poetry run invoke test --no-flake
poetry run invoke test --no-flake   # CI test entry point
poetry run pytest -q path/to/test.py # targeted pytest (coverage defaults still apply)
poetry run invoke test --deployment # credentialed post-deployment suite
cd docs && make html                 # Sphinx docs
```

`invoke test` first runs `flake8 .` unless `--no-flake`, then runs `tests/tibanna/` while excluding `tests/tibanna/post_deployment/`. Despite the "unit" CI label, much of this suite talks to real AWS. The `@pytest.mark.webtest` marker is descriptive only; the default configuration does not exclude it. CI obtains AWS credentials through GitHub OIDC and serializes Python 3.8 → 3.12 jobs to avoid shared-fixture races. The coverage floor is 25% and applies through `pyproject.toml`.

For offline tests:

- Set `AWS_ACCOUNT_NUMBER` and `TIBANNA_AWS_REGION`, and ensure boto3 sees credentials, before importing `tibanna`; otherwise `vars.py` may call STS or exit during collection. Dummy credentials/environment are appropriate only when every AWS call under test is mocked.
- Patch `boto3.client` in the module that uses it (for example `tibanna.ec2_utils.boto3.client`), because modules import boto3 independently.
- Constructing `Execution` calls `ec2.describe_instance_types`. Mock a response containing both `EbsInfo.EbsOptimizedSupport` and `ProcessorInfo.SupportedArchitectures`.
- Prefer narrow offline regression files under `tests/tibanna/unicorn/` or `tests/awsf3/`. Keep credentialed end-to-end checks under `tests/tibanna/post_deployment/` and never let tests mutate production AWS resources.
- Shell bootstrap tests extract and execute functions from the real script with AWS/system commands stubbed. Run `bash -n awsf3/aws_run_workflow_generic.sh`; use ShellCheck when changing shell.

The local Poetry executable may itself be unhealthy on older macOS setups if it links a removed Homebrew `libintl`; diagnose the environment rather than treating that loader failure as a repository test failure.

## CI and release conventions

- `.github/workflows/main.yml` runs the credentialed test command serially on Python 3.8–3.12 for pushes/PRs to `master`.
- Tag pushes trigger `.github/workflows/main-publish.yml`, which calls `make publish-for-ga` to publish the Python distribution. Keep `pyproject.toml`, `tibanna/_version.py`, `CHANGELOG.rst`, the worker image tag, bootstrap release tag, and pinned hashes coherent.
- `make publish-docker`/`scripts/publish-docker` build and push the multi-architecture Docker Hub image. `buildspec.yml` and `buildspec_amd_only.yml` build ECR images with Buildx. Publishing is an external side effect: do it only when explicitly authorized.
- Read the Docs deployment is manually triggered by `.github/workflows/main-deploy-docs.yml`.
- Preserve backwards compatibility in CLI signatures, JSON fields, S3 keys/markers, environment variables, AWS names, and postrun schema. Document user-visible changes in `CHANGELOG.rst` and the relevant RST page.

## Maintaining this file

Keep information that benefits most future sessions. Remove stale guidance when behavior changes. Point to the authoritative file, test, command, or documentation page instead of copying long lists. Add a sharp edge only when it is non-obvious, durable, and likely to prevent a real mistake.
