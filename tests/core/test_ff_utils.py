from core.ff_utils import ProcessedFileMetadata
from pytest import fixture


@fixture()
def proc_file_in_webdev():
    return {'status': 'released',
            'uuid': 'f6d5ba22-aaf9-48e9-8df4-bc5c131c96af',
            'file_format': 'normvector_juicerformat',
            'accession': '4DNFIRO3UX7I',
            'award': '/awards/1U01CA200059-01/',
            'lab': '/labs/4dn-dcic-lab/'}


def test_create_ProcessedFileMetadata_from_get(ff_keys, proc_file_in_webdev):
    # can use acc, uuid, @id, any valid url
    pf = ProcessedFileMetadata.get(proc_file_in_webdev['accession'], ff_keys)
    assert pf.__dict__ == proc_file_in_webdev
    assert type(pf) is ProcessedFileMetadata
