"""D1 regression tests for the verify_sha256 helper in
awsf3/aws_run_workflow_generic.sh - extracts the real function text (as with
the D2 handle_error tests) and exercises it with real bash, no AWS access
needed.
"""
import os
import re
import subprocess
import tempfile

SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), '..', '..', 'awsf3', 'aws_run_workflow_generic.sh'
)


def _read_script():
    with open(SCRIPT_PATH) as f:
        return f.read()


def _extract_function(name):
    content = _read_script()
    match = re.search(r'^' + re.escape(name) + r'\(\)\s*\{.*?^\}', content, re.DOTALL | re.MULTILINE)
    assert match, "could not find %s() function in aws_run_workflow_generic.sh" % name
    return match.group(0)


def _run_verify(expected, disable_verification=False, tamper=False):
    handle_error_src = _extract_function('handle_error')
    verify_src = _extract_function('verify_sha256')
    with tempfile.TemporaryDirectory() as marker_dir:
        target_file = os.path.join(marker_dir, 'downloaded_asset')
        with open(target_file, 'w') as f:
            f.write('some content' if not tamper else 'tampered content')

        script = """
set -u
send_error() {{ touch "{marker_dir}/send_error_called"; }}
send_log() {{ touch "{marker_dir}/send_log_called"; }}
shutdown() {{ touch "{marker_dir}/shutdown_called"; }}
SHUTDOWN_MIN=now
STATUS=0
DISABLE_SCRIPT_VERIFICATION={disable_verification}
exl() {{ "$@"; }}

{handle_error_src}

{verify_src}

verify_sha256 "{target_file}" "{expected}"
touch "{marker_dir}/reached_after_verify"
""".format(marker_dir=marker_dir, handle_error_src=handle_error_src, verify_src=verify_src,
           disable_verification=str(disable_verification).lower(), target_file=target_file, expected=expected)
        result = subprocess.run(['bash', '-c', script])
        markers = set(os.listdir(marker_dir))
        return result.returncode, markers


def _real_sha256(content):
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()


def test_verify_sha256_passes_on_matching_hash():
    exit_code, markers = _run_verify(_real_sha256('some content'))
    assert exit_code == 0
    assert 'reached_after_verify' in markers
    assert 'shutdown_called' not in markers


def test_verify_sha256_fails_closed_on_mismatch():
    """D1 acceptance criterion: a hash mismatch stops before proceeding
    (never reaches code after the verification call), sends a durable error
    signal, and requests instance termination."""
    exit_code, markers = _run_verify(_real_sha256('some content'), tamper=True)
    assert exit_code != 0
    assert 'reached_after_verify' not in markers
    assert 'send_error_called' in markers
    assert 'shutdown_called' in markers


def test_verify_sha256_fails_closed_on_missing_expected_value():
    """An unavailable expected hash (e.g. a caller that forgot to pass one)
    must not be silently treated as trust-on-first-use - it must fail closed
    just like a mismatch."""
    exit_code, markers = _run_verify('')
    assert exit_code != 0
    assert 'reached_after_verify' not in markers


def test_verify_sha256_dev_override_skips_verification():
    """The development-only DISABLE_SCRIPT_VERIFICATION override must be
    explicit and isolated - only takes effect when set, and clearly logged
    as a warning."""
    exit_code, markers = _run_verify(_real_sha256('some content'), disable_verification=True, tamper=True)
    assert exit_code == 0
    assert 'reached_after_verify' in markers
    assert 'shutdown_called' not in markers
