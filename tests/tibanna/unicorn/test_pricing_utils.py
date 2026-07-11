import json
import os
import pytest
from unittest.mock import patch, MagicMock
from tibanna.awsem import AwsemPostRunJson
from tibanna.pricing_utils import get_cost_estimate, update_cost_estimate_in_tsv


def _price_list_response(price):
    return {
        'PriceList': [json.dumps({
            'terms': {
                'OnDemand': {
                    'x': {
                        'priceDimensions': {
                            'y': {'pricePerUnit': {'USD': str(price)}}
                        }
                    }
                }
            }
        })]
    }


def _load_postrunjson(file_name):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(dir_path, '..', '..', '..', 'test_json', 'unicorn', file_name)
    with open(file_path, 'r') as file:
        postrunjsonstr = file.read().replace('\n', '')
    return AwsemPostRunJson(**json.loads(postrunjsonstr))


@patch('tibanna.pricing_utils.boto3')
def test_cost_estimate_scales_correctly_beyond_24h(mock_boto3):
    """C21 regression: (job_end - job_start).seconds truncates to the sub-day
    remainder, so a >24h job used to cost-estimate as if it were <1h long.
    total_seconds() must be used so cost scales with the full duration.
    """
    mock_pricing_client = MagicMock()
    mock_pricing_client.get_products.return_value = _price_list_response(0.0416)
    mock_boto3.client.return_value = mock_pricing_client

    short_job = _load_postrunjson('medium_nonspot.postrun.json')  # 5 min 53 sec
    long_job = _load_postrunjson('medium_nonspot_multiday.postrun.json')  # 25h 5 min 53 sec

    aws_price_overwrite = {'ec2_ondemand_price': 0.0416, 'ebs_root_storage_price': 0.08}
    short_cost, _ = get_cost_estimate(short_job, aws_price_overwrite=aws_price_overwrite)
    long_cost, _ = get_cost_estimate(long_job, aws_price_overwrite=aws_price_overwrite)

    short_duration_seconds = 353  # 16:58:05 -> 17:03:58
    long_duration_seconds = 90353  # 1 day + 353 seconds

    # Before the fix, `.seconds` truncated the long job's duration down to the
    # same 353-second remainder as the short job, making long_cost == short_cost.
    assert long_cost == pytest.approx(short_cost * (long_duration_seconds / short_duration_seconds))
    assert long_cost > short_cost * 250


@patch('tibanna.pricing_utils.does_key_exist')
def test_update_cost_estimate_in_tsv_missing_estimated_cost_type_row(mock_does_key_exist):
    """C24 regression: current_cost_estimate_type must be initialized before the
    scan loop so a metrics_report.tsv lacking an Estimated_Cost_Type row (the
    older-format case this retro-compat code exists to serve) doesn't raise
    NameError.
    """
    mock_does_key_exist.return_value = True
    tsv_without_estimated_cost_type = "Start_Time\t20210301-16:58:05-UTC\nInstance_Type\tt3.medium\n"
    with patch('tibanna.pricing_utils.read_s3', return_value=tsv_without_estimated_cost_type):
        with patch('tibanna.pricing_utils.put_object_s3') as mock_put:
            update_cost_estimate_in_tsv('somebucket', 'somejob', 0.05, "immediate estimate")
            assert mock_put.called
