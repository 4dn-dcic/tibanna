from invoke import task
from core.pony_utils import run_md5 as _run_md5
from core.pony_utils import batch_fastqc as _batch_fastqc
from core.pony_utils import run_fastqc as _run_fastqc


@task
def run_md5(ctx, env, accession, uuid):
    _run_md5(env=env, accession=accession, uuid=uuid)


@task
def batch_fastqc(ctx, env, batch_size=20):
    '''
    try to run fastqc on everythign that needs it ran
    '''
    _batch_fastqc(env=env, batch_size=batch_size)


@task
def run_fastqc(ctx, env, accession, uuid):
    _run_fastqc(env=env, accession=accession, uuid=uuid)
