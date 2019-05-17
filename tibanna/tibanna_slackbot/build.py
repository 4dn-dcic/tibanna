import boto3


class BuildStatus(object):

    name = '/ffstatus'

    def valid_user(self, slack_userid):
        return True

    def run(params):
        # get currently running builds
        # get status of last running build if none current
        # check aws if environment is ok
        # run gui tests to verify this thing appears to be up
        beanstalk = boto3.client('elasticbeanstalk', 'us-east-1')
        health = beanstalk.describe_environment_health(EnvironmentName='fourfront-webprod',
                                                       AttributeNames=['All', ])
        print(health)
