import boto3
from .utils import printlog


def get_items(table_name, primary_key, filter_key, filter_value, additional_keys=None):
    '''filter by filter_key=filter_value
    return all the values of primary_key and additional_keys.
    in the format of a list of dictionaries containing
    primary_key: value1, additional_key1: value2, additional_key2: value3, ...'''
    dd = boto3.client('dynamodb')

    if not additional_keys:
        additional_keys = []

    start_key = ''
    scan_input = {
        'TableName': table_name,
        'AttributesToGet': [primary_key] + additional_keys,
        'ScanFilter': {filter_key: {'AttributeValueList': [{'S': filter_value}],
                                    'ComparisonOperator': 'EQ'}}
    }
    entries = []

    while(True):
        if start_key:
            scan_input.update({'ExclusiveStartKey': {primary_key: {'S': start_key}}})
        res = dd.scan(**scan_input)
        if 'Items' in res and len(res['Items']) > 0:
            for item in res['Items']:
                entry = {primary_key: item[primary_key]['S']}
                for ak in additional_keys:
                    entry.update({ak: item[ak]['S']})
                entries.append(entry)
        if 'LastEvaluatedKey' in res and res['LastEvaluatedKey']:
            start_key = res['LastEvaluatedKey'][primary_key]['S']
        else:
            break
    return entries


def delete_items(table_name, primary_key, item_list):
    '''item_list is a list of dictionaries in the format of
    key1: value1, key2: value2, ...
    there has to be a primary key always.'''
    dd = boto3.client('dynamodb')
    for item in item_list:
        res2 = dd.delete_item(
            TableName=table_name,
            Key={primary_key: {'S': item[primary_key]}}
        )
    printlog("%d entries deleted from dynamodb." % len(item_list))
