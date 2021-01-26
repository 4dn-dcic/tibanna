import re


# custom exceptions
class AWSEMJobErrorException(Exception):
    """There is an error from a worklow run on the EC2 AWSEM instance."""
    pass


class AWSEMErrorHandler(object):

    def __init__(self):
        self.ErrorList = self._ErrorList  # initial error list, custom errors can be added

    class AWSEMError(object):
        def __init__(self, error_type, pattern_in_log, multiline=False):
            self.error_type = error_type
            if multiline:
                self.pattern_in_log = re.compile(pattern_in_log, re.MULTILINE)
            else:
                self.pattern_in_log = pattern_in_log

    def add_custom_errors(self, custom_err_list):
        """add custom errors to ErrorList.
        custom_err_list is a list of dictionaries w/ keys 'error_type', 'pattern', 'multiline'"""
        for err in custom_err_list:
            self.ErrorList.append(self.AWSEMError(err['error_type'], err['pattern'], err.get('multiline', False)))

    @property
    def _ErrorList(self):
        """add any specific error types with recognizable strings or patterns here.
        the order is important. The earlier ones are checked first and if there is a match,
        the later ones will not be checked."""
        return [
            # input download failure due to not enough disk space
            self.AWSEMError('Not enough space for input files', 'download failed: .+ No space left on device'),
            # Docker pull failure due to not enough root disk space
            self.AWSEMError('No space for docker', 'failed to register layer.+no space left on device'),
            # not enough disk space
            self.AWSEMError('Not enough space', '.+No space left on device'),
            # CWL missing input error
            self.AWSEMError('CWL missing input', 'Missing required input parameter\n.+\n', True),
            # Bucket access error
            self.AWSEMError('Bucket/file access denied', 'when calling the ListObjectsV2 operation: Access Denied')
        ]

    def parse_log(self, log):
        # for ex in self.AWSEMErrorExceptionList:
        for ex in self.ErrorList:
            res = re.search(ex.pattern_in_log, log)
            if res:
                match = res.string[res.regs[0][0]:res.regs[0][1]]
                match = re.sub('\n', ' ', match)  # \n not recognized and subsequent content is dropped from Exception
                match = re.sub(' +', ' ', match)
                msg = "%s: %s" % (ex.error_type, match)
                return AWSEMJobErrorException(msg)
        return

    @property
    def general_awsem_check_log_msg_template(self):
        return "check log using tibanna log --job-id=%s [--sfn=stepfunction]"

    def general_awsem_check_log_msg(self, job_id):
        return self.general_awsem_check_log_msg_template % job_id

    @property
    def general_awsem_error_msg_template(self):
        return "Job encountered an error " + self.general_awsem_check_log_msg_template

    def general_awsem_error_msg(self, job_id):
        return self.general_awsem_error_msg_template % job_id


class StillRunningException(Exception):
    """EC2 AWSEM instance is still running (job not complete)"""
    pass


class EC2StartingException(Exception):
    """EC2 AWSEM instance is still starting (job not complete)"""
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


class MalFormattedRunJsonException(Exception):
    pass


class MalFormattedPostRunJsonException(Exception):
    pass


class MetricRetrievalException(Exception):
    pass


class UnsupportedCWLVersionException(Exception):
    def __init__(self, message=None):
        if not message:
            message = "CWL draft3 is no longer supported. Please switched to v1"
        super().__init__(message)

