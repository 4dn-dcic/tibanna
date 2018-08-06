# -*- coding: utf-8 -*-
import os
import errno
import sys
import webbrowser
import json
from invoke import task, run
import boto3
import contextlib
import shutil
# from botocore.errorfactory import ExecutionAlreadyExists
from core.ec2_utils import AWS_S3_ROLE_NAME
from core.utils import AWS_REGION, AWS_ACCOUNT_NUMBER
from core.utils import run_workflow as _run_workflow
from core.utils import create_stepfunction as _create_stepfunction
from core.utils import _tibanna
from core.launch_utils import rerun as _rerun
from core.launch_utils import rerun_many as _rerun_many
from core.launch_utils import kill_all as _kill_all
from core.iam_utils import create_tibanna_iam
from core.iam_utils import get_bucket_role_name, get_lambda_role_name
from contextlib import contextmanager
import aws_lambda
import requests
import random

docs_dir = 'docs'
build_dir = os.path.join(docs_dir, '_build')
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
POSITIVE = 'https://gist.github.com/j1z0/bbed486d85fb4d64825065afbfb2e98f/raw/positive.txt'
NEGATIVE = 'https://gist.github.com/j1z0/bbed486d85fb4d64825065afbfb2e98f/raw/negative.txt'
AMI_ID_CWL_V1 = 'ami-31caa14e'
AMI_ID_CWL_DRAFT3 = 'ami-cfb14bb5'
TIBANNA_REPO_NAME = os.environ.get('TIBANNA_REPO_NAME', '4dn-dcic/tibanna')
TIBANNA_REPO_BRANCH = os.environ.get('TIBANNA_REPO_BRANCH', 'master')
TIBANNA_PROFILE_ACCESS_KEY = os.environ.get('TIBANNA_PROFILE_ACCESS_KEY', '')
TIBANNA_PROFILE_SECRET_KEY = os.environ.get('TIBANNA_PROFILE_SECRET_KEY', '')
UNICORN_LAMBDAS = ['run_task_awsem', 'check_task_awsem']


def get_random_line_in_gist(url):
    listing = requests.get(url)
    return random.choice(listing.text.split("\n"))


@task
def play(ctx, positive=False):
    type_url = POSITIVE if positive else NEGATIVE
    # no spaces in url
    media_url = '%20'.join(get_random_line_in_gist(type_url).split())
    run("vlc -I rc %s --play-and-exit -q" % (media_url))


@contextmanager
def setenv(**kwargs):
    # Backup
    prev = {}
    for k, v in kwargs.items():
        if k in os.environ:
            prev[k] = os.environ[k]
        os.environ[k] = v

    yield

    # Restore
    for k in kwargs.keys():
        if k in prev:
            os.environ[k] = prev[k]
        else:
            del os.environ[k]


def get_all_core_lambdas():
    return [
        'validate_md5_s3_trigger',
        'start_run_awsem',
        'run_task_awsem',
        'check_task_awsem',
        'update_ffmeta_awsem',
        'run_workflow',
    ]


def env_list(name):
    # don't set this as a global, since not all tasks require it
    secret = os.environ.get("SECRET")
    if secret is None:
        raise RuntimeError("SECRET should be defined in env")
    envlist = {
        'run_workflow': {'SECRET': secret,
                         'TIBANNA_AWS_REGION': AWS_REGION,
                         'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
        'start_run_awsem': {'SECRET': secret,
                            'TIBANNA_AWS_REGION': AWS_REGION,
                            'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
        'run_task_awsem': {'AMI_ID_CWL_V1': AMI_ID_CWL_V1,
                           'AMI_ID_CWL_DRAFT3': AMI_ID_CWL_DRAFT3,
                           'TIBANNA_REPO_NAME': TIBANNA_REPO_NAME,
                           'TIBANNA_REPO_BRANCH': TIBANNA_REPO_BRANCH,
                           'TIBANNA_AWS_REGION': AWS_REGION,
                           'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER,
                           'AWS_S3_ROLE_NAME': AWS_S3_ROLE_NAME},
        'check_task_awsem': {'TIBANNA_AWS_REGION': AWS_REGION,
                             'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
        'update_ffmeta_awsem': {'SECRET': secret,
                                'TIBANNA_AWS_REGION': AWS_REGION,
                                'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER},
        'validate_md5_s3_trigger': {'SECRET': secret,
                                    'TIBANNA_AWS_REGION': AWS_REGION,
                                    'AWS_ACCOUNT_NUMBER': AWS_ACCOUNT_NUMBER}
    }
    if TIBANNA_PROFILE_ACCESS_KEY and TIBANNA_PROFILE_SECRET_KEY:
        envlist['run_task_awsem'].update({
            'TIBANNA_PROFILE_ACCESS_KEY': TIBANNA_PROFILE_ACCESS_KEY,
            'TIBANNA_PROFILE_SECRET_KEY': TIBANNA_PROFILE_SECRET_KEY}
        )
    return envlist.get(name, '')


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
    # don't set this as a global, since not all tasks require it
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


def copytree(src, dst, symlinks=False, ignore=None):
    skipfiles = ['.coverage', 'dist', 'htmlcov', '__init__.pyc', 'coverage.xml', 'service.pyc']
    for item in os.listdir(src):
        src_file = os.path.join(src, item)
        dst_file = os.path.join(dst, item)
        if src_file.split('/')[-1] in skipfiles:
            print("skipping file %s" % src_file)
            continue
        if os.path.isdir(src_file):
            mkdir(dst_file)
            shutil.copytree(src_file, dst_file, symlinks, ignore)
        else:
            shutil.copy2(src_file, dst_file)


def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


@task
def new_lambda(ctx, name, base='run_task_sbg'):
    '''
    create a new lambda by copy from a base one and replacing some core strings.
    '''
    src_dir = './core/%s' % base
    dest_dir = './core/%s' % name
    mkdir(dest_dir)
    copytree(src=src_dir, dst=dest_dir)
    chdir(dest_dir)
    # TODO: awk some lines here...


@task
def get_url(ctx, prj_name='lambda_sbg'):
    url = run('cd %s; chalice url' % prj_name).stdout.strip('\n')
    return url


@task
def test(ctx, watch=False, last_failing=False, no_flake=False, k='',  extra='',
         ignore='', ignore_pony=False, ignore_webdev=False):
    """Run the tests.
    Note: --watch requires pytest-xdist to be installed.
    """
    import pytest
    if not no_flake:
        flake(ctx)
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
        args.append('tests/core/pony')
    if ignore_webdev:
        args.append('--ignore')
        args.append('tests/core/pony/test_webdev.py')
    retcode = pytest.main(args)
    try:
        good = True if retcode == 0 else False
        play(ctx, good)
    except:
        print("install vlc for more exciting test runs...")
    if retcode != 0:
        print("test failed exiting")
        sys.exit(retcode)
    return retcode


@task
def flake(ctx):
    """Run flake8 on codebase."""
    run('flake8 .', echo=True)
    print("flake8 passed!!!")


@task
def clean(ctx):
    run("rm -rf build")
    run("rm -rf dist")
    print("Cleaned up.")


@task
def deploy_chalice(ctx, name='lambda_sbg', version=None):
    print("deploying %s" % (name))
    print("a chalice based lambda api")
    run("cd %s; chalice deploy" % (name))


@task
def deploy_core(ctx, name, version=None, tests=False, suffix=None, usergroup=None):
    print("preparing for deploy...")
    if tests:
        print("running tests...")
        if test(ctx) != 0:
            print("tests need to pass first before deploy")
            return
    else:
        print("skipping tests. execute with --tests flag to run them")
    if name == 'all':
        names = get_all_core_lambdas()

    elif name == 'unicorn':
        names = UNICORN_LAMBDAS
    else:
        names = [name, ]
    print('deploying the following lambdas: %s' % names)

    # dist directores are the enemy, clean them all
    for name in get_all_core_lambdas():
        print("cleaning house before deploying")
        with chdir("./core/%s" % (name)):
            clean(ctx)

    for name in names:
        print("=" * 20, "Deploying lambda", name, "=" * 20)
        with chdir("./core/%s" % (name)):
            print("clean up previous builds.")
            clean(ctx)
            print("building lambda package")
            deploy_lambda_package(ctx, name, suffix=suffix, usergroup=usergroup)
            # need to clean up all dist, otherwise, installing local package takes forever
            clean(ctx)
        print("next get version information")
        # version = update_version(ctx, version)
        print("then tag the release in git")
        # git_tag(ctx, version, "new production release %s" % (version))
        # print("Build is now triggered for production deployment of %s "
        #      "check travis for build status" % (version))


@task
def deploy_lambda_package(ctx, name, suffix=None, usergroup=None):
    # create the temporary local dev lambda directories
    if usergroup:
        if suffix:
            suffix = usergroup + suffix
        else:
            suffix = usergroup
    if suffix:
        new_name = name + '_' + suffix
        new_src = '../' + new_name
        cmd_mkdir = "rm -fr %s; mkdir -p %s" % (new_src, new_src)
        cmd_copy = "cp -r * %s" % new_src
        cmd_cd = "cd %s" % new_src
        cmd_modify_cfg = "sed 's/%s/%s/g' config.yaml > config.yaml#" % (name, new_name)
        cmd_replace_cfg = "mv config.yaml# config.yaml"
        cmd = ';'.join([cmd_mkdir, cmd_copy, cmd_cd, cmd_modify_cfg, cmd_replace_cfg])
        print(cmd)
        run(cmd)
    else:
        new_name = name
        new_src = '../' + new_name
    # use the lightweight requirements for the lambdas to simplify deployment
    if name in UNICORN_LAMBDAS:
        requirements_file = '../../requirements-lambda-unicorn.txt'
    else:
        requirements_file = '../../requirements-lambda-pony.txt'
    with chdir(new_src):
        aws_lambda.deploy(os.getcwd(), local_package='../..', requirements=requirements_file)
    # add environment variables
    lambda_update_config = {'FunctionName': new_name}
    envs = env_list(name)
    if envs:
        lambda_update_config['Environment'] = {'Variables': envs}
    if name == 'run_task_awsem':
        if usergroup:
            lambda_update_config['Environment']['Variables']['AWS_S3_ROLE_NAME'] \
                = get_bucket_role_name('tibanna_' + usergroup)
        else:
            lambda_update_config['Environment']['Variables']['AWS_S3_ROLE_NAME'] = 'S3_access'  # 4dn-dcic default(temp)
    # add role
    print('name=%s' % name)
    if name in ['run_task_awsem', 'check_task_awsem']:
        role_arn_prefix = 'arn:aws:iam::' + AWS_ACCOUNT_NUMBER + ':role/'
        if usergroup:
            role_arn = role_arn_prefix + get_lambda_role_name('tibanna_' + usergroup, name)
        else:
            role_arn = role_arn_prefix + 'lambda_full_s3'  # 4dn-dcic default(temp)
            print(role_arn)
        lambda_update_config['Role'] = role_arn
    client = boto3.client('lambda')
    resp = client.update_function_configuration(**lambda_update_config)
    print(resp)
    # delete the temporary local dev lambda directories
    if suffix:
        old_src = '../' + name
        run('cd %s; rm -rf %s' % (old_src, new_src))


def _PROD():
    return _tbenv() == 'PROD'


def _tbenv(env_data=None):
    if env_data and env_data.get('env'):
        return env_data('env')
    return os.environ.get('ENV_NAME')


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
def run_workflow(ctx, input_json='', workflow=''):
    with open(input_json) as input_file:
        data = json.load(input_file)
        if workflow == '':
            resp = _run_workflow(data)
        else:
            resp = _run_workflow(data, workflow=workflow)
        run('open %s' % resp[_tibanna]['url'])


@task
def setup_tibanna_env(ctx, buckets='', usergroup_tag='default'):
    '''The very first function to run as admin to set up environment on AWS'''
    print("setting up tibanna environment on AWS...")
    bucket_names = buckets.split(',')
    tibanna_policy_prefix = create_tibanna_iam(AWS_ACCOUNT_NUMBER, bucket_names,
                                               usergroup_tag, AWS_REGION)
    tibanna_usergroup = tibanna_policy_prefix.replace("tibanna_", "")
    print("Tibanna usergroup %s has been created on AWS." % tibanna_usergroup)


@task
def deploy_tibanna(ctx, suffix=None, sfn_type='pony', usergroup=None, version=None, tests=False):
    print("creating a new workflow...")
    if sfn_type not in ['pony', 'unicorn']:
        raise Exception("Invalid sfn_type : it must be either pony or unicorn.")
    res = _create_stepfunction(suffix, sfn_type, usergroup=usergroup)
    print(res)
    print("deploying lambdas...")
    if sfn_type == 'pony':
        deploy_core(ctx, 'all', version=version, tests=tests, suffix=suffix, usergroup=usergroup)
    else:
        deploy_core(ctx, 'unicorn', version=version, tests=tests, suffix=suffix, usergroup=usergroup)


@task
def travis(ctx, branch='production', owner='4dn-dcic', repo_name='fourfront'):
    # lambdas use logging
    import logging
    logging.basicConfig()

    from core.travis_deploy.service import handler as travis
    data = {'branch': branch,
            'repo_owner': owner,
            'repo_name': repo_name
            }
    travis(data, None)
    # print("https://travis-ci.org/%s" % res.json()['repository']['slug'])


@task(aliases=['notebooks'])
def notebook(ctx):
    """
    Start IPython notebook server.
    """
    with setenv(PYTHONPATH='{root}/core:{root}:{root}/tests'.format(root=ROOT_DIR),
                JUPYTER_CONFIG_DIR='{root}/notebooks'.format(root=ROOT_DIR)):

        os.chdir('notebooks')

        # Need pty=True to let Ctrl-C kill the notebook server. Shrugs.
        try:
            run('jupyter nbextension enable --py widgetsnbextension')
            run('jupyter notebook --ip=*', pty=True)
        except KeyboardInterrupt:
            pass
        print("If notebook does not open on your chorme automagically, try adding this to your bash_profie")
        print("export BROWSER=/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome")
        print("*for MacOS and Chrome only")


@task
def rerun(ctx, exec_arn, workflow='tibanna_pony'):
    """ rerun a specific job"""
    _rerun(exec_arn, workflow=workflow)


@task
def kill_all(ctx, workflow='tibanna_pony', region=AWS_REGION, acc=AWS_ACCOUNT_NUMBER):
    """ killing all the running jobs"""
    _kill_all(workflow=workflow, region=region, acc=acc)


@task
def rerun_many(ctx, workflow='tibanna_pony', stopdate='13Feb2018', stophour=13,
               stopminute=0, offset=5, sleeptime=5, status='FAILED'):
    """Reruns step function jobs that failed after a given time point (stopdate, stophour (24-hour format), stopminute)
    By default, stophour is in EST. This can be changed by setting a different offset (default 5)
    Sleeptime is sleep time in seconds between rerun submissions.
    By default, it reruns only 'FAILED' runs, but this can be changed by resetting status.
    examples)
    rerun_many('tibanna_pony-dev')
    rerun_many('tibanna_pony', stopdate= '14Feb2018', stophour=14, stopminute=20)
    """
    _rerun_many(workflow=workflow, stopdate=stopdate, stophour=stophour,
                stopminute=stopminute, offset=offset, sleeptime=sleeptime, status=status)
