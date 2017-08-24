#!/usr/bin/python
import json
import sys
import os
import time
json_old=sys.argv[1]
json_new=sys.argv[2]
 
## read old json file
with open(json_old, 'r') as json_old_f:
     dict=json.load(json_old_f)

## add end time, status, instance_id
dict['Job']['end_time'] = time.strftime("%Y%m%d-%H:%M:%S-%Z")
dict['Job']['status'] = os.getenv('JOB_STATUS')
dict['Job']['instance_id'] = os.getenv('INSTANCE_ID')
 
## write to new json file
with open(json_new, 'w') as json_new_f:
     json.dump(dict, json_new_f, indent=4, sort_keys=True)
