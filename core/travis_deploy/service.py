# -*- coding: utf-8 -*-
import requests
import os
import logging
import json


logger = logging.getLogger()
logger.setLevel(logging.INFO)

travis_key = os.environ.get('travis_key')
gh_token = os.environ.get('gh_token')


def get_default(data, key):
    return data.get(key, os.environ.get(key, None))


def handler(event, context):
    # get data
    branch = get_default(event, 'branch')
    repo_owner = get_default(event, 'repo_owner')
    repo_name = get_default(event, 'repo_name')

    # auth with travis through gh token
    # requests.post('https://https://api.travis-ci.org
    body = {
            "request": {
                "message": "Your Tibanna triggered build has started.  Have a nice day! :)",
                "branch": branch,
                "config": {
                    "global": {
                       "tibanna_deploy": "True"
                    }
                }
              }
            }

    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json',
               'Travis-API-Version': '3',
               'User-Agent': 'tibanna/0.1.0',
               'Authorization': 'token %s' % travis_key
               }

    url = 'https://api.travis-ci.org/repo/%s%s%s/requests' % (repo_owner, '%2F', repo_name)

    resp = requests.post(url, headers=headers, data=json.dumps(body))

    try:
        logger.info(resp)
        logger.info(resp.text)
        logger.info(resp.json())
    except:
        pass

    return resp
