import json
import sys
import os
import time
json_old = sys.argv[1]
json_new = sys.argv[2]

# read old json file
with open(json_old, 'r') as json_old_f:
    Dict = json.load(json_old_f)

# add end time, status, instance_id
Dict['Job']['end_time'] = time.strftime("%Y%m%d-%H:%M:%S-%Z")
Dict['Job']['status'] = os.getenv('JOB_STATUS')
Dict['Job']['instance_id'] = os.getenv('INSTANCE_ID')
Dict['Job']['total_input_size'] = os.getenv('INPUTSIZE')
Dict['Job']['total_tmp_size'] = os.getenv('TEMPSIZE')
Dict['Job']['total_output_size'] = os.getenv('OUTPUTSIZE')

# write to new json file
with open(json_new, 'w') as json_new_f:
    json.dump(Dict, json_new_f, indent=4, sort_keys=True)
