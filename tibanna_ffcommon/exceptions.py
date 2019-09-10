from tibanna.exceptions import *
import traceback


class TibannaStartException(Exception):
    """Error connecting to get the access key from s3"""
    pass


class FdnConnectionException(Exception):
    """There is an error connecting to the 4DN portal"""
    pass


class MalFormattedFFInputException(Exception):
    """There is an error with pony/zebra input json format"""
    pass


def exception_coordinator(lambda_name, metadata_only_func):
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
                              TibannaStartException, FdnConnectionException,
                              DependencyStillRunningException, EC2InstanceLimitWaitException]

        def wrapper(event, context):
            if context:
                logger.info(context)
            logger.info(event)
            if lambda_name in event.get('skip', []):
                logger.info('skipping %s since skip was set in input_json' % lambda_name)
                return event
            elif event.get('push_error_to_end', False) and event.get('error', False) \
                    and lambda_name != 'update_ffmeta':
                logger.info('skipping %s since a value for "error" is in input json '
                            'and lambda is not update_ffmeta_awsem' % lambda_name)
                return event
            elif event.get('metadata_only', False):
                return metadata_only_func(event)
            # else
            try:
                return function(event, context)
            except Exception as e:
                if type(e) in ignored_exceptions:
                    raise e
                    # update ff_meta to error status
                elif lambda_name == 'update_ffmeta':
                    # for last step just pit out error
                    if 'error' in event:
                        error_msg = "error from earlier step: %s" % event["error"]
                    else:
                        error_msg = "error from update_ffmeta: %s." % str(e) + \
                                    "Full traceback: %s" % traceback.format_exc()
                    raise Exception(error_msg)
                elif not event.get('push_error_to_end', False):
                    raise e
                # else
                if e.__class__ == AWSEMJobErrorException:
                    error_msg = 'Error on step: %s: %s' % (lambda_name, str(e))
                elif e.__class__ == EC2UnintendedTerminationException:
                    error_msg = 'EC2 unintended termination error on step: %s: %s' % (lambda_name, str(e))
                elif e.__class__ == EC2IdleException:
                    error_msg = 'EC2 Idle error on step: %s: %s' % (lambda_name, str(e))
                else:
                    error_msg = 'Error on step: %s. Full traceback: %s' % (lambda_name, traceback.format_exc())
                event['error'] = error_msg
                logger.info(error_msg)
                return event
        return wrapper
    return decorator
