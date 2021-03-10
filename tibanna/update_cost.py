# -*- coding: utf-8 -*-
import boto3
import json
import copy
from . import create_logger
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from .core import API

logger = create_logger(__name__)


def update_cost(input_json):
    return UpdateCost(input_json).run()


class UpdateCost(object):
    API = API

    def __init__(self, input_json):
        self.input_json = copy.deepcopy(input_json)

    def run(self):
        # s3 bucket that stores the output
        bucket_name = self.input_json['log_bucket']
        sfn_arn = self.input_json['sfn_arn'] # Execution ARN of the Unicorn stepfunction
        aws_region = self.input_json['aws_region']
        jobid = self.input_json['job_id']

        postrun_json = "%s.postrun.json" % jobid

        done ={ 
            "done": False,
            "message": ""
        }

        try:
            client = boto3.client('stepfunctions', region_name=aws_region)
            unicorn_execution = client.describe_execution(executionArn=sfn_arn)
        except Exception as e:
            done["done"] = True
            done["message"] = "Could not get information about the unicorn step function. Exiting."
            return done

        if(unicorn_execution["status"] == "RUNNING"):
            # Unicorn job hasn't finished, go to the 'wait' step in the cost updater step function
            done["message"] = "Job is still running"
            return done

        end_time = unicorn_execution["stopDate"] # Should be UTC time
        now = datetime.now(tzutc())

        if end_time + timedelta(hours=24*3) < now:
            # If it did not work for 3 days after the job finished, give up
            done["done"] = True
            done["message"] = "Cost could not be retrieved after 3 days. Stopping."
            return done

        cost = self.API().cost(jobid, update_tsv=False)

        if(cost > 0.0):
            self.API().cost(jobid, update_tsv=True) 
            self.API().plot_metrics(jobid, open_browser=False, force_upload=True, update_html_only=True)
            done["done"] = True
            return done 

        else:
            done["message"] = "Cost not yet available."
            return done



