# -*- coding: utf-8 -*-
import os
import sys
import webbrowser
import json
from invoke import task, run
import boto3
import contextlib

docs_dir = 'docs'
build_dir = os.path.join(docs_dir, '_build')


@contextlib.contextmanager
def chdir(dirname=None):
    curdir = os.getcwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
            yield
    finally:
        os.chdir(curdir)


def upload(keyname, data, s3bucket, secret=None):

    if secret is None:
        secret = os.environ.get("SECRET")
        if secret is None:
            raise RuntimeError("SECRET should be defined in env")

    s3 = boto3.client('s3')
    s3.put_object(Bucket=s3bucket,
                  Key=keyname,
                  Body=data,
                  SSECustomerKey=secret,
                  SSECustomerAlgorithm='AES256')


@task
def loc(ctx):
    """
    Count lines-of-code.
    """
    excludes = ['/tests/', '/Data_files', 'Submit4DN.egg-info', 'docs', 'htmlcov',
                'README.md', 'README.rst', '.eggs']

    run('find . -iname "*py" | grep -v {} | xargs wc -l | sort -n'.format(
        ' '.join('-e ' + e for e in excludes)))


@task
def get_url(ctx, prj_name='lambda_sbg'):
    url = run('cd %s; chalice url' % prj_name).stdout.strip('\n')
    return url


@task
def test(ctx, watch=False, last_failing=False, no_flake=False, extra=''):
    """Run the tests.
    Note: --watch requires pytest-xdist to be installed.
    """
    from os import path

    import pytest
    if not no_flake:
        flake(ctx)
    args = ['-rxs', ]
    args.append(extra)
    if watch:
        args.append('-f')
    if last_failing:
        args.append('--lf')
    retcode = pytest.main(args)
    try:
        home = path.expanduser("~")
        if retcode == 0:
            sndfile = os.path.join(home, "code", "snd", "zenyatta", "You_Have_Done_Well.ogg")
        else:
            sndfile = os.path.join(home, "code", "snd", "zenyatta", "Darkness\ Falls.ogg")
        print(sndfile)
        run("vlc -I rc %s --play-and-exit -q" % (sndfile))
    except:
        pass
    return(retcode)


@task
def flake(ctx):
    """Run flake8 on codebase."""
    run('flake8 .', echo=True)
    print("flake8 passed!!!")


@task
def clean(ctx):
    run("rm -rf build")
    print("Cleaned up.")


@task
def deploy_chalice(ctx, name='lambda_sbg', version=None):
    print("deploying %s" % (name))
    print("a chalice based lambda api")
    run("cd %s; chalice deploy" % (name))


def get_all_core_lambdas():
    return ['start_run_sbg',
            'check_import_sbg',
            ]


@task
def deploy_core(ctx, name, version=None):
    print("preparing for deploy...")
    print("make sure tests pass")
    if test(ctx) != 0:
        print("tests need to pass first before deploy")
        return
    if name == 'all':
        names = get_all_core_lambdas()
        print(names)
    else:
        names = [name, ]

    for name in names:
        print("=" * 20, "Deploying lambda", name, "=" * 20)
        with chdir("./core/%s" % (name)):
            print("clean up previous builds.")
            clean(ctx)
            print("building lambda package")
            deploy_lambda_package(ctx, name)
        print("next get version information")
        # version = update_version(ctx, version)
        print("then tag the release in git")
        # git_tag(ctx, version, "new production release %s" % (version))
        # print("Build is now triggered for production deployment of %s "
        #      "check travis for build status" % (version))


@task
def deploy_lambda_package(ctx, name):
    run('lambda deploy  --local-package ../..')


@task
def upload_sbg_keys(ctx, sbgkey=None):
    if sbgkey is None:
        sbgkey = os.environ.get('SBG_KEY')
    return upload_keys(ctx, sbgkey, 'sbgkey')


def upload_keys(ctx, keys, name):
    s3bucket = 'elasticbeanstalk-encoded-4dn-system'
    if os.environ.get('ENV_NAME') == 'PROD':
        s3bucket = 'elasticbeanstalk-production-encoded-4dn-system'
    print("uploading sbkey to %s as %s" % (s3bucket, name))
    upload(name, keys, s3bucket)


@task
def upload_s3_keys(ctx, key=None, secret=None):
    if key is None:
        key = os.environ.get("SBG_S3_KEY")
    if secret is None:
        secret = os.environ.get("SBG_S3_SECRET")

    pckt = {'key': key,
            'secret': secret}
    return upload_keys(ctx, json.dumps(pckt), 'sbgs3key')


@task
def update_version(ctx, version=None):
    from wranglertools._version import __version__
    print("Current version is ", __version__)
    if version is None:
        version = input("What version would you like to set for new release (please use x.x.x / "
                        " semantic versioning): ")

    # read the versions file
    lines = []
    with open("wranglertools/_version.py") as readfile:
        lines = readfile.readlines()

    if lines:
        with open("wranglertools/_version.py", 'w') as writefile:
            lines[-1] = '__version__ = "%s"\n' % (version.strip())
            writefile.writelines(lines)

    run("git add wranglertools/_version.py")
    run("git commit -m 'version bump'")
    print("version updated to", version)
    return version


@task
def git_tag(ctx, tag_name, msg):
    run('git tag -a %s -m "%s"' % (tag_name, msg))
    run('git push --tags')
    run('git push')


@task
def clean_docs(ctx):
    run("rm -rf %s" % build_dir, echo=True)


@task
def browse_docs(ctx):
    path = os.path.join(build_dir, 'index.html')
    webbrowser.open_new_tab(path)


@task
def docs(ctx, clean=False, browse=False, watch=False):
    """Build the docs."""
    if clean:
        clean_docs(ctx)
    run("sphinx-build %s %s" % (docs_dir, build_dir), echo=True)
    if browse:
        browse_docs(ctx)
    if watch:
        watch_docs(ctx)


@task
def watch_docs(ctx):
    """Run build the docs when a file changes."""
    try:
        import sphinx_autobuild  # noqa
    except ImportError:
        print('ERROR: watch task requires the sphinx_autobuild package.')
        print('Install it with:')
        print('    pip install sphinx-autobuild')
        sys.exit(1)
    run('sphinx-autobuild {0} {1} --watch {2}'.format(
        docs_dir, build_dir, '4DNWranglerTools'), echo=True, pty=True)


@task
def readme(ctx, browse=False):
    run('rst2html.py README.rst > README.html')
    if browse:
        webbrowser.open_new_tab('README.html')


@task
def publish(ctx, test=False):
    """Publish to the cheeseshop."""
    clean(ctx)
    if test:
        run('python setup.py register -r test sdist bdist_wheel', echo=True)
        run('twine upload dist/* -r test', echo=True)
    else:
        run('python setup.py register sdist bdist_wheel', echo=True)
        run('twine upload dist/*', echo=True)
