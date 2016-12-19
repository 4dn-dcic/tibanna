# -*- coding: utf-8 -*-
import os
import sys
import webbrowser

from invoke import task, run
import boto3


docs_dir = 'docs'
build_dir = os.path.join(docs_dir, '_build')


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
def test(ctx, watch=False, last_failing=False, no_flake=False):
    """Run the tests.
    Note: --watch requires pytest-xdist to be installed.
    """
    import pytest
    if not no_flake:
        flake(ctx)
    args = []
    if watch:
        args.append('-f')
    if last_failing:
        args.append('--lf')
    retcode = pytest.main(args)
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
def deploy(ctx, name, version=None):
    print("preparing for deploy...")
    print("first lets clean everythign up.")
    clean(ctx)
    print("now lets make sure the tests pass")
    test(ctx)
    build_lambda_package(ctx, name)
    print("next get version information")
    # version = update_version(ctx, version)
    print("then tag the release in git")
    # git_tag(ctx, version, "new production release %s" % (version))
    # print("Build is now triggered for production deployment of %s "
    #      "check travis for build status" % (version))


@task
def build_lambda_package(ctx, name):
    run('cd %s; lambda deploy' % name)


@task
def upload_keys(ctx):
    sbgkey = os.environ.get('SBG_KEY')
    if not sbgkey:
        print("no sbg key to deploy")
    else:
        s3bucket = 'elasticbeanstalk-encoded-4dn-system'
        if os.environ.get('ENV_NAME') == 'PROD':
            s3bucket = 'elasticbeanstalk-production-encoded-4dn-system'
        print("uploading sbkey to %s" % (s3bucket))
        upload('sbgkey', sbgkey, s3bucket)


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

@task
def set_lambda_s3_perms(ctx):
    '''
    aws lambda add-permissions \
    --function-name 
    #9e7e144b18724b65641286dfa355edb64c424035706bd1674e9096ee77422a45

