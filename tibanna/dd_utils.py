import boto3
from .utils import printlog


def item2dict(item):
    '''convert a dynamoDB-style item to a regular dictionary'''
    return {k: list(v.values())[0] for k, v in item.items()}


def does_dynamo_table_exist(tablename):
    try:
        res = boto3.client('dynamodb').describe_table(
            TableName=tablename
        )
        if res:
            return True
        else:
            raise Exception("error describing table %s" % tablename)
    except Exception as e:
        if 'Requested resource not found' in str(e):
            return False
        else:
            raise Exception("error describing table %s" % tablename)


def create_dynamo_table(tablename, keyname):
    if does_dynamo_table_exist(tablename):
        print("dynamodb table %s already exists. skip creating db" % tablename)
    else:
        response = boto3.client('dynamodb').create_table(
            TableName=tablename,
            AttributeDefinitions=[
                {
                     'AttributeName': keyname,
                     'AttributeType': 'S'
                }
            ],
            KeySchema=[
                {
                    'AttributeName': keyname,
                    'KeyType': 'HASH'
                 }
            ],
            BillingMode='PAY_PER_REQUEST'
        )


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


def delete_items(table_name, primary_key, item_list, verbose=True):
    '''item_list is a list of dictionaries in the format of
    key1: value1, key2: value2, ...
    there has to be a primary key always.'''
    dd = boto3.client('dynamodb')
    for item in item_list:
        res2 = dd.delete_item(
            TableName=table_name,
            Key={primary_key: {'S': item[primary_key]}}
        )
    if verbose:
        printlog("%d entries deleted from dynamodb." % len(item_list))
