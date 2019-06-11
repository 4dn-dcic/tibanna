# custom exceptions
class StillRunningException(Exception):
    """EC2 AWSEM instance is still running (job not complete)"""
    pass


class EC2StartingException(Exception):
    """EC2 AWSEM instance is still starting (job not complete)"""
    pass


class AWSEMJobErrorException(Exception):
    """There is an error from a worklow run on the EC2 AWSEM instance"""
    pass


class DependencyStillRunningException(Exception):
    pass


class DependencyFailedException(Exception):
    pass


class EC2LaunchException(Exception):
    pass


class EC2UnintendedTerminationException(Exception):
    pass


class EC2IdleException(Exception):
    pass


class EC2InstanceLimitException(Exception):
    pass


class EC2InstanceLimitWaitException(Exception):
    pass


class MissingFieldInInputJsonException(Exception):
    pass


class MalFormattedInputJsonException(Exception):
    pass
