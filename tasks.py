import sys
import pytest
from invoke import run, task


@task
def test(ctx, watch=False, last_failing=False, no_flake=False, k='',  extra='',
         ignore='', ignore_pony=False, no_post=False, deployment=False):
    """Run the tests.
    Note: --watch requires pytest-xdist to be installed.
    """
    if deployment:
        retcode = pytest.main(['--workers', '100', 'tests/tibanna/post_deployment'])
    else:
        if not no_flake:
            flake()
        args = ['-rxs', ]
        if k:
            args.append('-k %s' % k)
        args.append(extra)
        if watch:
            args.append('-f')
        else:
            args.append('--cov-report')
            args.append('xml')
            args.append('--cov-report')
            args.append('html')
        if last_failing:
            args.append('--lf')
        if ignore:
            args.append('--ignore')
            args.append(ignore)
        args.append('tests/tibanna/')
        retcode = pytest.main(args)
    if retcode != 0:
        print("test failed exiting")
        sys.exit(retcode)
    return retcode


def flake():
    """Run flake8 on codebase."""
    run('flake8 .', echo=True)
    print("flake8 passed!!!")
