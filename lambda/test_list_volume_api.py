#!/usr/bin/python
import requests
import json

sbg_base_url = "https://api.sbgenomics.com/v2"
sbg_project_id = "4dn-dcic/dev"



def format_response (response):
  return json.dumps(json.loads(response.text), indent=4)


def list_volumes (token):
  volume_url = sbg_base_url + "/storage/volumes/"
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = {}
  response = requests.get(volume_url, headers=header, data=json.dumps(data))
  print(format_response(response))


def get_details_of_volume (token, volume_id):
  volume_url = sbg_base_url + "/storage/volumes/" + volume_id
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = { "volume_id" : volume_id }
  response = requests.get(volume_url, headers=header, data=json.dumps(data))
  print(format_response(response))


def import_volume_content (token, volume_id, source_filename, dest_filename):
  import_url = sbg_base_url + "/storage/imports"
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = { 
    "source":{  
      "volume": volume_id,
      "location": source_filename
    },
    "destination": {  
      "project": sbg_project_id,
      "name": dest_filename
    },
    "overwrite": False 
  }
  response = requests.post(import_url, headers=header, data=json.dumps(data))
  print(format_response(response))
  return(response.json()['id'])


def get_details_of_import (token, import_id):
  import_url = sbg_base_url + "/storage/imports/" + import_id
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = { "import_id" : import_id }
  response = requests.get(import_url, headers=header, data=json.dumps(data))
  print(format_response(response))
  

def export_to_volume (token, source_file_id, volume_id, dest_filename):
  export_url = sbg_base_url + "/storage/exports/"
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = { 
    "source": {
      "file": source_file_id
    },
    "destination": {
      "volume": volume_id,
      "location": dest_filename
    }
  }
  response = requests.post(export_url, headers=header, data=json.dumps(data))
  print(format_response(response))
  return(response.json()['id'])


def get_details_of_export (token, export_id):
  export_url = sbg_base_url + "/storage/exports/" + export_id
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = { "export_id" : export_id }
  response = requests.get(export_url, headers=header, data=json.dumps(data))
  print(format_response(response))


def create_volumes (token, volume_name, bucket_name, bucket_object_prefix, access_mode, public_key, secret_key):
  volume_url = sbg_base_url + "/storage/volumes/"
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = { 
    "name" : volume_name, 
    "description" : "some volume" , 
    "service" : {
       "type": "s3",
       "bucket": bucket_name,
       "prefix": bucket_object_prefix,
       "credentials": {
         "access_key_id": public_key,
         "secret_access_key": secret_key
       },
       "properties": {
         "sse_algorithm": "AES256"
       }
    },
    "access_mode" : access_mode
  }
  response = requests.post(volume_url, headers=header, data=json.dumps(data))
  print(format_response(response))



if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fun with 7Bridges")
    parser.add_argument('-t','--token', help='your 7Bridges api access token')
    parser.add_argument('-b','--bucket', help='your S3 bucket name')
    parser.add_argument('-p','--prefix', help='your S3 bucket object prefix')
    parser.add_argument('-k','--key', help='your public access key')
    parser.add_argument('-s','--secret_key', help='your secret access key')
    parser.add_argument('-v','--volume_id', help='volume_id')
    parser.add_argument('-n','--volume_name', help='volume_name')
    parser.add_argument('-f','--source_filename', help='source file to be imported to sbg')
    parser.add_argument('-ii','--import_id', help='import_id for an import job')
    parser.add_argument('-ei','--export_id', help='export_id for an export job')
    parser.add_argument('-F','--source_file_id', help='source file id for an export job')
    parser.add_argument('-d','--dest_filename', help='destination file name for an export job')
    parser.add_argument('-a','--access_mode', help='access_mode (RO or RW)')
    args = parser.parse_args()
    create_volumes(args.token, args.volume_name, args.bucket, args.prefix, args.access_mode, args.key, args.secret_key)
    list_volumes(args.token)
    get_details_of_volume (args.token, args.volume_id)
    import_id=import_volume_content(args.token, args.volume_id, args.source_filename, args.source_filename)
    if args.import_id:
      import_id = args.import_id
    get_details_of_import (args.token, import_id)

    #export_id = export_to_volume (args.token, args.source_file_id, args.volume_id, args.dest_filename)
    if args.export_id:
      export_id = args.export_id
    #get_details_of_export (args.token, export_id)

