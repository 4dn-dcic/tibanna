from __future__ import print_function
from core.iam_utils import get_stepfunction_role_name
import logging
import traceback

###########################################
# These utils exclusively live in Tibanna #
###########################################


###########################
# Config
###########################


# logger
LOG = logging.getLogger(__name__)


# custom exceptions to control retry logic in step functions
class StillRunningException(Exception):
    pass


class EC2StartingException(Exception):
    pass


class AWSEMJobErrorException(Exception):
    pass


class TibannaStartException(Exception):
    pass


class FdnConnectionException(Exception):
    pass


def powerup(lambda_name, metadata_only_func):
    '''
    friendly wrapper for your lambda functions, based on input_json / event comming in...
    1. Logs basic input for all functions
    2. if 'skip' key == 'lambda_name', skip the function
    3. catch exceptions raised by labmda, and if not in  list of ignored exceptions, added
       the exception to output json
    4. 'metadata' only parameter, if set to true, just create metadata instead of run workflow

    '''
    def decorator(function):
        import logging
        logging.basicConfig()
        logger = logging.getLogger('logger')
        ignored_exceptions = [EC2StartingException, StillRunningException,
                              TibannaStartException, FdnConnectionException]

        def wrapper(event, context):
            logger.info(context)
            logger.info(event)
            if lambda_name in event.get('skip', []):
                logger.info('skipping %s since skip was set in input_json' % lambda_name)
                return event
            elif event.get('error', False) and lambda_name != 'update_ffmeta_awsem':
                logger.info('skipping %s since a value for "error" is in input json '
                            'and lambda is not update_ffmeta_awsem' % lambda_name)
                return event
            elif event.get('metadata_only', False):
                return metadata_only_func(event)
            else:
                try:
                    return function(event, context)
                except Exception as e:
                    if type(e) in ignored_exceptions:
                        raise e
                        # update ff_meta to error status
                    elif lambda_name == 'update_ffmeta_awsem':
                        # for last step just pit out error
                        raise e
                    else:
                        error_msg = 'Error on step: %s. Full traceback: %s' % (lambda_name, traceback.format_exc())
                        event['error'] = error_msg
                        logger.info(error_msg)
                        return event
        return wrapper
    return decorator
