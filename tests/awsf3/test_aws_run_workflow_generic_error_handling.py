"""D2 regression tests for awsf3/aws_run_workflow_generic.sh's error handling.

These run real bash (no AWS/Docker/mount access needed): the handle_error
tests extract the actual handle_error() function text from the script and
exercise it directly with send_error/send_log/shutdown stubbed out, mirroring
the local reproduction the audit used. The remaining tests are structural
assertions on the script source proving each of the pre-mount, post-mount,
Docker-pull, and Docker-run failure points route through the fixed
fail-closed handle_error rather than merely scheduling a shutdown.
"""
import os
import re
import subprocess
import tempfile

SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), '..', '..', 'awsf3', 'aws_run_workflow_generic.sh'
)


def _extract_handle_error_function():
    with open(SCRIPT_PATH) as f:
        content = f.read()
    match = re.search(r'^handle_error\(\)\s*\{.*?^\}', content, re.DOTALL | re.MULTILINE)
    assert match, "could not find handle_error() function in aws_run_workflow_generic.sh"
    return match.group(0)


def _run_handle_error(errcode_arg):
    """Run the real handle_error() function (extracted from the script) in a
    subshell with send_error/send_log/shutdown stubbed to drop marker files.
    Returns (subshell_exit_code, set_of_markers_created).
    """
    handle_error_src = _extract_handle_error_function()
    with tempfile.TemporaryDirectory() as marker_dir:
        script = """
set -u
send_error() {{ touch "{marker_dir}/send_error_called"; }}
send_log() {{ touch "{marker_dir}/send_log_called"; }}
shutdown() {{ touch "{marker_dir}/shutdown_called"; }}
SHUTDOWN_MIN=now
STATUS=0

{handle_error_src}

handle_error {errcode_arg}
touch "{marker_dir}/reached_after_handler"
""".format(marker_dir=marker_dir, handle_error_src=handle_error_src, errcode_arg=errcode_arg)
        result = subprocess.run(['bash', '-c', script])
        markers = set(os.listdir(marker_dir))
        return result.returncode, markers


def test_handle_error_fails_closed_on_nonzero_code():
    """D2 core regression: a nonzero error code must send the error/log
    markers, request shutdown, AND exit immediately - the calling script must
    never reach any code after handle_error.
    """
    exit_code, markers = _run_handle_error(7)
    assert exit_code == 7
    assert 'send_error_called' in markers
    assert 'send_log_called' in markers
    assert 'shutdown_called' in markers
    assert 'reached_after_handler' not in markers


def test_handle_error_does_not_exit_on_success():
    exit_code, markers = _run_handle_error(0)
    assert exit_code == 0
    assert 'send_error_called' not in markers
    assert 'send_log_called' not in markers
    assert 'shutdown_called' not in markers
    assert 'reached_after_handler' in markers


def test_handle_error_with_missing_argument_still_fails_closed():
    """D2 regression: a bare `handle_error` call (no error code argument, as
    used at two call sites before this fix) must not silently evaluate
    `[ "" -ne 0 ]` as false and skip error reporting - it must default to a
    real error and still fail closed.
    """
    handle_error_src = _extract_handle_error_function()
    with tempfile.TemporaryDirectory() as marker_dir:
        script = """
set -u
send_error() {{ touch "{marker_dir}/send_error_called"; }}
send_log() {{ touch "{marker_dir}/send_log_called"; }}
shutdown() {{ touch "{marker_dir}/shutdown_called"; }}
SHUTDOWN_MIN=now
STATUS=0

{handle_error_src}

handle_error
touch "{marker_dir}/reached_after_handler"
""".format(marker_dir=marker_dir, handle_error_src=handle_error_src)
        result = subprocess.run(['bash', '-c', script])
        markers = set(os.listdir(marker_dir))
    assert result.returncode != 0
    assert 'send_error_called' in markers
    assert 'reached_after_handler' not in markers


def _read_script():
    with open(SCRIPT_PATH) as f:
        return f.read()


def test_no_bare_handle_error_calls_remain():
    """Pre-mount regression: every handle_error call site must pass an
    explicit error code (a bare `handle_error;` used to rely on the buggy
    `[ "" -ne 0 ]` comparison, which silently skipped error reporting)."""
    content = _read_script()
    bare_calls = re.findall(r'handle_error\s*;', content)
    assert bare_calls == []


def test_missing_log_bucket_exits_before_continuing():
    """Pre-mount regression: the log-bucket-not-defined branch cannot call
    send_error/send_log (LOGBUCKET is unset), but it must still exit instead
    of merely scheduling a shutdown and falling through."""
    content = _read_script()
    match = re.search(
        r'if \[ -z "\$LOGBUCKET" \]; then(.*?)\nfi', content, re.DOTALL
    )
    assert match, "could not find the LOGBUCKET check"
    branch = match.group(1)
    assert re.search(r'\bexit\b', branch)


def test_docker_pull_exhaustion_fails_closed():
    """Docker-pull regression: if all retry attempts fail, the script must
    call handle_error (fail closed) instead of silently falling through to
    `docker run` with a missing/stale image."""
    content = _read_script()
    assert 'pull_success' in content
    match = re.search(
        r'if \[ "\$pull_success" != true \]; then(.*?)fi', content, re.DOTALL
    )
    assert match, "could not find the docker-pull failure check"
    assert 'handle_error' in match.group(1)


def test_docker_run_failure_routes_through_handle_error():
    """Docker-run regression: the result of `docker run` (the workload
    execution) must be checked and routed through handle_error."""
    content = _read_script()
    docker_run_section = content[content.index('docker run --privileged'):]
    assert re.search(r'^handle_error \$\?', docker_run_section, re.MULTILINE)


def test_errfile_has_pre_mount_and_post_mount_paths():
    """D2 regression: ERRFILE must point at a path that exists before the EBS
    volume is mounted/formatted (under the home directory, which exists at
    boot), and switch to the EBS-backed path only after the mount succeeds -
    otherwise a pre-mount failure can't persist a durable error marker."""
    content = _read_script()
    assert re.search(r'export ERRFILE1=/home/ubuntu/\$JOBID\.error', content)
    assert re.search(r'export ERRFILE2=\$LOCAL_OUTDIR/\$JOBID\.error', content)
    assert 'export ERRFILE=$ERRFILE1' in content
    # the switch to ERRFILE2 must happen at/after local outdir creation, not before
    mkdir_idx = content.index('exl mkdir -p $LOCAL_OUTDIR')
    switch_idx = content.index('export ERRFILE=$ERRFILE2')
    assert switch_idx > mkdir_idx
