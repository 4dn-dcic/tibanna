import pytest
import os
from tibanna.cw_utils import (
    TibannaResource
)


def test_extract_metrics_data():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_name = os.path.join(dir_path, '..', '..', 'files', 'metrics', 'metrics.tsv')
    with open(file_name, 'r') as file:
        metrics_str = file.read()
        columns_js, columns, data_js, data = TibannaResource.extract_metrics_data(metrics_str)
        assert len(columns) == 6
        assert "interval" not in columns
        assert len(columns_js) == 152
        assert len(data_js) == 5901
        assert "[[251.03125,308.83203125,470.3046875" in data_js
        assert len(data.keys()) == 7
        assert len(data['max_mem_used_MB']) == 60
        assert data['min_mem_available_MB'][4] == "743.23828125"



