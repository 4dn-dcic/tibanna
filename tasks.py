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
from core.utils import run_workflow as _run_workflow
from core.utils import create_stepfunction as _create_stepfunction
from core.utils import _tibanna_settings, Tibanna, get_files_to_match
from core.utils import _tibanna, s3Utils
from core.ff_utils import get_metadata
from core.launch_utils import rerun as _rerun
from core.launch_utils import rerun_many as _rerun_many
from core.launch_utils import kill_all as _kill_all
from core.ff_utils import HIGLASS_SERVER, HIGLASS_USER, HIGLASS_PASS, SECRET
from contextlib import contextmanager
import aws_lambda
from time import sleep
import requests
import random

docs_dir = 'docs'
build_dir = os.path.join(docs_dir, '_build')
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
POSITIVE = 'https://gist.github.com/j1z0/bbed486d85fb4d64825065afbfb2e98f/raw/positive.txt'
NEGATIVE = 'https://gist.github.com/j1z0/bbed486d85fb4d64825065afbfb2e98f/raw/negative.txt'


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
    envlist = {
        'start_run_awsem': {'SECRET': SECRET},
        'update_ffmeta_awsem': {'SECRET': SECRET,
                                'HIGLASS_SERVER': HIGLASS_SERVER,
                                'HIGLASS_USER': HIGLASS_USER,
                                'HIGLASS_PASS': HIGLASS_PASS}
    }
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
def test(ctx, watch=False, last_failing=False, no_flake=False, k='',  extra=''):
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
def deploy_core(ctx, name, version=None, no_tests=False, suffix=None):
    print("preparing for deploy...")
    print("make sure tests pass")
    if no_tests is False:
        if test(ctx) != 0:
            print("tests need to pass first before deploy")
            return
    if name == 'all':
        names = get_all_core_lambdas()
        print(names)
    else:
        names = [name, ]

    # dist directores are the enemy, clean the all
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
            deploy_lambda_package(ctx, name, suffix=suffix)
            # need to clean up all dist, otherwise, installing local package takes forever
            clean(ctx)
        print("next get version information")
        # version = update_version(ctx, version)
        print("then tag the release in git")
        # git_tag(ctx, version, "new production release %s" % (version))
        # print("Build is now triggered for production deployment of %s "
        #      "check travis for build status" % (version))


@task
def deploy_lambda_package(ctx, name, suffix):
    # create the temporary local dev lambda directories
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
    with chdir(new_src):
        aws_lambda.deploy(os.getcwd(), local_package='../..', requirements='../../requirements.txt')
    # add environment variables
    lambda_update_config = {'FunctionName': new_name}
    envs = env_list(name)
    if envs:
        lambda_update_config['Environment'] = {'Variables': envs}
    client = boto3.client('lambda')
    resp = client.update_function_configuration(**lambda_update_config)
    print(resp)
    # delete the temporary local dev lambda directories
    if suffix:
        old_src = '../' + name
        run('cd %s; rm -rf %s' % (old_src, new_src))


@task
def upload_sbg_keys(ctx, sbgkey=None, env='fourfront-webprod'):
    if sbgkey is None:
        sbgkey = os.environ.get('SBG_KEY')

    if sbgkey is None:
        print("error no sbgkey found in environment")
        return 1

    s3bucket = "elasticbeanstalk-%s-system" % env
    return upload_keys(ctx, sbgkey, 'sbgkey', s3bucket)


def _PROD():
    return _tbenv() == 'PROD'


def _tbenv(env_data=None):
    if env_data and env_data.get('env'):
        return env_data('env')
    return os.environ.get('ENV_NAME')


def upload_keys(ctx, keys, name, s3bucket=None):
    if not s3bucket:
        s3bucket = 'elasticbeanstalk-fourfront-webprod-system'
    print("uploading sbkey to %s as %s" % (s3bucket, name))
    upload(name, keys, s3bucket)


@task
def upload_s3_keys(ctx, key=None, secret=None, env="fourfront-webprod"):
    if key is None:
        key = os.environ.get("SBG_S3_KEY")
    if secret is None:
        secret = os.environ.get("SBG_S3_SECRET")

    pckt = {'key': key,
            'secret': secret}
    s3bucket = "elasticbeanstalk-%s-system" % env
    return upload_keys(ctx, json.dumps(pckt), 'sbgs3key', s3bucket)


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
def run_md5(ctx, env, objectkey, uuid):
    input_json = make_input(env=env, workflow='md5', object_key=objectkey, uuid=uuid)
    return _run_workflow(input_json, objectkey)


@task
def batch_md5(ctx, env, batch_size=20):
    '''
    try to run fastqc on everythign that needs it ran
    '''
    tibanna = Tibanna(env=env)
    file_bucket = tibanna.s3.outfile_bucket.replace('wfoutput', 'files')
    tibanna.s3.outfile_bucket = file_bucket
    uploaded_files = get_files_to_match(tibanna,
                                        "search/?type=File&status=uploading",
                                        frame="embedded")

    limited_files = uploaded_files['@graph']

    files_processed = 0
    total_files = len(limited_files)
    skipped_files = 0
    for ufile in limited_files:
        if files_processed >= batch_size:
            print("we have done enough here")
            sys.exit(0)

        if not tibanna.s3.does_key_exist(ufile.get('upload_key')):
            print("******** no file for %s on s3, can't run md5, skipping" %
                  ufile.get('accession'))
            skipped_files += 1
            continue
        else:
            print("running md5 for %s" % ufile.get('accession'))
            run_md5(ctx, env, ufile.get('accession'), ufile.get('uuid'))
            files_processed += 1
            sleep(10)
            if files_processed % 10 == 0:
                sleep(60)

    print("Total Files: %s, Processed Files: %s, Skipped Files: %s" %
          (total_files, files_processed, skipped_files))


@task
def batch_fastqc(ctx, env, batch_size=20):
    '''
    try to run fastqc on everythign that needs it ran
    '''
    files_processed = 0
    files_skipped = 0

    # handle ctrl-c
    import signal

    def report(signum, frame):
        print("Processed %s files, skipped %s files" % (files_processed, files_skipped))
        sys.exit(-1)

    signal.signal(signal.SIGINT, report)

    tibanna = Tibanna(env=env)
    uploaded_files = get_files_to_match(tibanna,
                                        "search/?type=File&status=uploaded&limit=%s" % batch_size,
                                        frame="embedded")

    # TODO: need to change submit 4dn to not overwrite my limit
    if len(uploaded_files['@graph']) > batch_size:
        limited_files = uploaded_files['@graph'][:batch_size]
    else:
        limited_files = uploaded_files['@graph']

    for ufile in limited_files:
        fastqc_run = False
        for wfrun in ufile.get('workflow_run_inputs', []):
            if 'fastqc' in wfrun:
                fastqc_run = True
        if not fastqc_run:
            print("running fastqc for %s" % ufile.get('accession'))
            run_fastqc(ctx, env, ufile.get('accession'), ufile.get('uuid'))
            files_processed += 1
        else:
            print("******** fastqc already run for %s skipping" % ufile.get('accession'))
            files_skipped += 1
        sleep(5)
        if files_processed % 10 == 0:
            sleep(60)

    print("Processed %s files, skipped %s files" % (files_processed, files_skipped))


@task
def run_fastqc(ctx, env, accession, uuid):
    if not accession.endswith(".fastq.gz"):
        accession += ".fastq.gz"
    input_json = make_input(env=env, workflow='fastqc-0-11-4-1', object_key=accession, uuid=uuid)
    return _run_workflow(input_json, accession)


_workflows = {'md5':
              {'uuid': 'd3f25cd3-e726-4b3c-a022-48f844474b41',
               'arg_name': 'input_file'
               },
              'fastqc-0-11-4-1':
              {'uuid': '2324ad76-ff37-4157-8bcc-3ce72b7dace9',
               'arg_name': 'input_fastq'
               },
              }


def calc_ebs_size(bucket, key):
    s3 = s3Utils(bucket, bucket, bucket)
    size = s3.get_file_size(key, bucket, add_gb=3, size_in_gb=True)
    if size < 10:
        size = 10
    return size


def make_input(env, workflow, object_key, uuid):
    bucket = "elasticbeanstalk-%s-files" % env
    output_bucket = "elasticbeanstalk-%s-wfoutput" % env
    workflow_uuid = _workflows[workflow]['uuid']
    workflow_arg_name = _workflows[workflow]['arg_name']

    data = {"parameters": {},
            "app_name": workflow,
            "workflow_uuid": workflow_uuid,
            "input_files": [
                {"workflow_argument_name": workflow_arg_name,
                 "bucket_name": bucket,
                 "uuid": uuid,
                 "object_key": object_key,
                 }
             ],
            "output_bucket": output_bucket,
            "config": {
                "ebs_type": "io1",
                "json_bucket": "4dn-aws-pipeline-run-json",
                "ebs_iops": 500,
                "shutdown_min": 30,
                "s3_access_arn": "arn:aws:iam::643366669028:instance-profile/S3_access",
                "ami_id": "ami-cfb14bb5",
                "copy_to_s3": True,
                "script_url": "https://raw.githubusercontent.com/4dn-dcic/tibanna/master/awsf/",
                "launch_instance": True,
                "password": "thisisnotmypassword",
                "log_bucket": "tibanna-output",
                "key_name": ""
              },
            }
    data.update(_tibanna_settings({'run_id': str(object_key),
                                   'run_type': workflow,
                                   'env': env,
                                   }))
    return data


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
def deploy_tibanna(ctx, suffix='dev', sfn_type='pony', version=None, no_tests=False):
    print("creating a new workflow..")
    res = _create_stepfunction(suffix, sfn_type)
    print(res)
    print("deploying lambdas..")
    deploy_core(ctx, 'all', version=version, no_tests=no_tests, suffix=suffix)


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
def kill_all(ctx, workflow='tibanna_pony', region='us-east-1', acc='643366669028'):
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
