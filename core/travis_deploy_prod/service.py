# -*- coding: utf-8 -*-
import requests
import os
import logging
import json


logger = logging.getLogger()
logger.setLevel(logging.INFO)
travis_key = os.environ.get('travis_key')


def get_default(data, key):
    return data.get(key, os.environ.get(key, None))


def handler(event, context):
    # get data
    branch = get_default(event, 'branch')
    repo_owner = get_default(event, 'repo_owner')
    repo_name = get_default(event, 'repo_name')
    print("trigger build for %s/%s on branch %s" % (repo_owner, repo_name, branch))

    # overwrite the before_install section (travis doesn't allow append)
    # by adding the tibanna-deploy env variable, which will trigger the deploy
    body = {
            "request": {
                "message": "Tibanna triggered build to webprod has started.  Have a nice day! :)",
                "branch": branch,
                "config": {
                    "before_install": ["export tibanna_deploy=fourfront-webprod",
                                       "echo $tibanna_deploy",
                                       "postgres --version",
                                       "initdb --version",
                                       "nvm install 4",
                                       "node --version",
                                       "npm config set python /usr/bin/python2.7"
                                       ]
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
