# import boto3
import json
import logging
import os
import requests
import random

# from base64 import b64decode
from urlparse import parse_qs
from core.utils import run_workflow, _tibanna, TIBANNA_DEFAULT_STEP_FUNCTION_NAME


# ENCRYPTED_EXPECTED_TOKEN = os.environ['kmsEncryptedToken']

# kms = boto3.client('kms')
# expected_token = kms.decrypt(CiphertextBlob=b64decode(ENCRYPTED_EXPECTED_TOKEN))['Plaintext']
expected_token = os.environ.get('slack_token')

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info(event)
    logger.info(context)
    params = parse_qs(event['body'])
    token = params['token'][0]
    if token != expected_token:
        logger.error("Request token (%s) does not match expected", token)
        return respond(Exception('Invalid request token'))

    # user = params['user_name'][0]
    command = params['command'][0]
    # channel = params['channel_name'][0]
    command_text = params['text'][0]

    # list of commands mapped to functions, function should do its thing and return
    # appropriate results that will be passed back to user
    slash_commands = {'/runwf': run_wf}

    response = slash_commands.get(command, not_sure)(command_text)
    print(response)
    return respond(None, response)


def run_wf(command):
    args = {"workflow": command,
            "input_json": '',
            }

    logger.info("in run_wf ars are %s" % args)
    # some defaults stuff here
    if args['workflow'].startswith("hic_parta"):
        args['workflow'] = TIBANNA_DEFAULT_STEP_FUNCTION_NAME
        args['input_json'] = test_hic_data()
    else:
        return not_sure()

    run_data = run_workflow(**args)
    run_name = run_data[_tibanna]['run_name']
    run_url = run_data[_tibanna]["url"]

    # make a whitty response
    terms = ['take off', 'blast off', 'running']
    random_giphy = giphy(random.choice(terms))

    # return an attachment?
    slack_args = {'title': "workflow run %s started!" % run_name,
                  'title_link': run_url,
                  'text': "Your workflow is running. See status here %s" % run_url,
                  'image_url': random_giphy,
                  }

    response = {'attachments': [make_slack_attachment(**slack_args)]}
    return response


def make_slack_attachment(title="Workflow started",
                          title_link="http:/github.com/hms-dbmi",
                          text="Your Workflow is running. Thanks for using tibanna.",
                          image_url='',
                          fallback="We,re running your workflow now!",
                          color="#764FA5"):
    return {
        "fallback": fallback,
        "title": title,
        "title_link": title_link,
        "text": text,
        "image_url": image_url,
        "color": color,
    }


def test_hic_data():
    return {
          "input_files": [
                  {
                            "bucket_name": "encoded-4dn-files",
                            "object_key": "4DNFI067AFHV.fastq.gz",
                            "uuid": "46e82a90-49e5-4c33-afab-9ec90d65cca1",
                            "workflow_argument_name": "fastq1"
                          },
                  {
                            "bucket_name": "encoded-4dn-files",
                            "object_key": "4DNFI067AFHX.fastq.gz",
                            "uuid": "46e82a90-49e5-4c33-afab-9ec90d65cca2",
                            "workflow_argument_name": "fastq2"
                          },
                  {
                            "bucket_name": "encoded-4dn-files",
                            "object_key": "4DNFIZQZ39L9.bwaIndex.tgz",
                            "uuid": "1f53df95-4cf3-41cc-971d-81bb16c486dd",
                            "workflow_argument_name": "bwa_index"
                          }
                ],
          "workflow_uuid": "02d636b9-d82d-4da9-950c-2ca994a0943e",
          "app_name": "hi-c-processing-parta/9",
          "parameters": {
                  "nThreads": 8
                },
          "output_bucket": "elasticbeanstalk-encoded-4dn-wfoutput-files"
    }


def not_sure(*args, **kwargs):
    responses = ["Sorry. I'm not sure what you mean.",
                 "No idea what your talking about... tibanna out!",
                 "you talking to me?",
                 "I no speako your language-o",
                 "Nope, try again",
                 "What kinda arguments are those?",
                 "Did you read the docs?, oh I don't have docs?  Well good luck then...",
                 ]
    return random.choice(responses)


def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }


def giphy(query, apikey="dc6zaTOxFJmzC"):
    from random import randint
    args = {'query': query,
            'apikey': apikey,
            'offset': randint(0, 10)
            }
    query = "q={query}&api_key={apikey}&limit=1&offset={offset}&raiting=pg".format(**args)

    api_url = "http://api.giphy.com/v1/gifs/search?%s" % (query)
    res = requests.get(api_url).json()
    img_url = res['data'][0]['images']['downsized']['url']
    return img_url
