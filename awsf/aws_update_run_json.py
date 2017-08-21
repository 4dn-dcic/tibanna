#!/usr/bin/python
import json
import sys
import os
import time
json_old=sys.argv[1]
json_out=sys.argv[2]
json_new=sys.argv[3]
 
## read old json file
with open(json_old, 'r') as json_old_f:
     dict=json.load(json_old_f)

## read cwl output json file
with open(json_out, 'r') as json_out_f:
     dict['Job']['Output'].append(json.load(json_out_f))

## add end time
date=time.strftime("%Y%m%d-%H:%M:%S-%Z")
dict['Job']['end_time']=date
 
## add status
status=os.getenv('JOB_STATUS')
dict['Job']['status']=status
 
## write to new json file
with open(json_new, 'w') as json_new_f:
     json.dump(dict, json_new_f, indent=4, sort_keys=True)
