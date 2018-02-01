from core.ff_utils import ProcessedFileMetadata
import pytest
import mock


@pytest.fixture()
def proc_file_in_webdev():
    return {'status': 'released',
            'uuid': 'f6d5ba22-aaf9-48e9-8df4-bc5c131c96af',
            'file_format': 'normvector_juicerformat',
            'accession': '4DNFIRO3UX7I',
            'award': '/awards/1U01CA200059-01/',
            'lab': '/labs/4dn-dcic-lab/'}


def test_create_ProcessedFileMetadata_from_get_error_if_no_at_type(ff_keys, proc_file_in_webdev):
    # can use acc, uuid, @id, any valid url
    with mock.patch('core.ff_utils.get_metadata', return_value=proc_file_in_webdev):
        with pytest.raises(Exception) as expinfo:
            ProcessedFileMetadata.get(proc_file_in_webdev['accession'], ff_keys)
        assert "only load ProcessedFiles" in str(expinfo.value)


def test_create_ProcessedFileMetadata_from_get(ff_keys, proc_file_in_webdev):
    # can use acc, uuid, @id, any valid url
    file_with_type = proc_file_in_webdev.copy()
    file_with_type['@type'] = ['FileProcessed', 'Item', 'whatever']
    with mock.patch('core.ff_utils.get_metadata', return_value=file_with_type) as ff:
        pf = ProcessedFileMetadata.get(proc_file_in_webdev['accession'], ff_keys)
        assert pf.__dict__ == proc_file_in_webdev
        assert type(pf) is ProcessedFileMetadata
        ff.was_called_once()
