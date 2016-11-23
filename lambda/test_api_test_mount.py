import requests
import json

url = "https://kglml0pmwa.execute-api.us-east-1.amazonaws.com/dev"

def test_mount_lambda(token):

    headers = {'X-SBG-Auth-Token': token,
               'Content-Type': 'application/json'}

    #payload
    data = {"bucket_name" : "4dn-dcic-sbg",
            "object_key" : "arrow7.jpg"
           }

    resp = requests.post(url, headers=headers, data=json.dumps(data))
    print(resp.json())

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="lambda test")
    parser.add_argument('--token', help='your 4dn access token')
    args = parser.parse_args()
    test_mount_lambda(args.token)
