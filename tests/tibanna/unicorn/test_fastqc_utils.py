from tibanna import fastqc_utils
import pytest
import os

DIR = os.path.dirname(__file__)
FASTQC_DIR = os.path.join(DIR, '..', '..', 'files', 'fastqc_report')
PAIRSQC_DIR = os.path.join(DIR, '..', '..', 'files', 'pairsqc_report')


@pytest.fixture
def summary():
    return open(os.path.join(FASTQC_DIR, 'summary.txt')).read()


@pytest.fixture
def data():
    return open(os.path.join(FASTQC_DIR, 'fastqc_data.txt')).read()


@pytest.fixture
def pairsqc_summary():
    return open(os.path.join(PAIRSQC_DIR, "sample1.summary.out")).read()


@pytest.fixture
def quality_metric_pairsqc_schema():
    qc_schema = {'Total reads': {'type': 'number'},
                 'Cis/Trans ratio': {'type': 'number'},
                 'convergence': {'type': 'string'}}
    return qc_schema


@pytest.fixture
def quality_metric_fastqc_schema():
    qc_schema = {'Total Sequences': {'type': 'number'},
                 'Kmer Content': {'type': 'string'},
                 'overall_quality_status': {'type': 'string'}}
    return qc_schema


def test_parse_qc_table_pairsqc(pairsqc_summary, quality_metric_pairsqc_schema):
    meta = fastqc_utils.parse_qc_table([pairsqc_summary], url='test_url',
                                       qc_schema=quality_metric_pairsqc_schema)
    assert meta['Total reads'] == 651962
    assert meta['Cis/Trans ratio'] == 64.141
    assert meta['convergence'] == 'Good'


def test_parse_qc_table_fastqc(summary, data, quality_metric_fastqc_schema):
    meta = fastqc_utils.parse_qc_table([summary, data], url='test_url',
                                       qc_schema=quality_metric_fastqc_schema)
    assert meta['Total Sequences'] == 557747
    assert meta['Kmer Content'] == 'WARN'
    assert meta['url'] == 'test_url'
    assert meta['overall_quality_status'] == 'PASS'
