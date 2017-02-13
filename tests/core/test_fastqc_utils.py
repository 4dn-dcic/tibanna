from core import fastqc_utils
import pytest
import os

DIR = os.path.dirname(__file__)
FASTQC_DIR = os.path.join(DIR, '..', 'files', 'fastqc_report')


@pytest.fixture
def summary():
    return open(os.path.join(FASTQC_DIR, 'summary.txt')).read()


@pytest.fixture
def data():
    return open(os.path.join(FASTQC_DIR, 'fastqc_data.txt')).read()


def test_parse_fastqc(summary, data):
    meta = fastqc_utils.parse_fastqc(summary, data, url='test_url')
    assert meta['url'] == 'test_url'
