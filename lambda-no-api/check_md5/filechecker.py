from __future__ import print_function

import json
import urllib
import boto3
import os

print('Loading function')

s3 = boto3.client('s3')
SYS_BUCKET = 'elasticbeanstalk-encoded-4dn-system'
keyfile_name = 'illnevertell'


def get_access_keys():
    # Share secret encrypted S3 File
    response = s3.get_object(Bucket=SYS_BUCKET,
                  Key=keyfile_name,
                  SSECustomerKey=os.environ.get("SECRET"),
                  SSECustomerAlgorithm='AES256')
    akey = response['Body'].read()
    return json.loads(akey)['default']


def verify_md5(event, context):
    akeys = get_access_keys()
    return "42"

    # print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        print("CONTENT TYPE: " + response['ContentType'])
        return response['ContentType']
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e

if __name__ == "__main__":
    print(get_access_keys())
