import sys
import pytest
from invoke import run


def test(watch=False, last_failing=False, no_flake=False, k='',  extra='',
         ignore='', ignore_pony=False, ignore_webdev=False):
    """Run the tests.
    Note: --watch requires pytest-xdist to be installed.
    """
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
    if ignore_pony:
        args.append('--ignore')
        args.append('tests/tibanna/pony')
    if ignore_webdev:
        args.append('--ignore')
        args.append('tests/tibanna/pony/test_webdev.py')
    retcode = pytest.main(args)
    if retcode != 0:
        print("test failed exiting")
        sys.exit(retcode)
    return retcode


def flake():
    """Run flake8 on codebase."""
    run('flake8 .', echo=True)
    print("flake8 passed!!!")
