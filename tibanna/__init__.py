import logging


class TibannaLoggingFormatter(logging.Formatter):

    verbose_fmt  = "[%(name)s] %(levelname)s: %(asctime)s - %(message)s"
    info_fmt = "%(message)s"

    def format(self, record):
        if record.levelno == logging.INFO:
            tmpformatter = logging.Formatter(TibannaLoggingFormatter.info_fmt)
        else:
            tmpformatter = logging.Formatter(TibannaLoggingFormatter.verbose_fmt)
            tmpformatter.datefmt = '%y-%m-%d %H:%M:%S'
        return tmpformatter.format(record)


def create_logger(name='root'):
    logger = logging.getLogger(name)  

    # configuring severity level
    logger.setLevel(logging.DEBUG)

    # configuring format requires creating a handler first
    log_handler = logging.StreamHandler()
    log_formatter = TibannaLoggingFormatter()
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)

    return logger
