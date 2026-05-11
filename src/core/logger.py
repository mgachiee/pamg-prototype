import logging

logger = logging.getLogger(__name__)

class Logger:
    """
    A simple logger class to handle logging throughout the PAMG system.
    This can be expanded in the future to include different log levels, file logging, etc.
    """
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )

    def info(self, message: str):
        logger.info(message)

    def warning(self, message: str):
        logger.warning(message)

    def error(self, message: str):
        logger.error(message)

    def debug(self, message: str):
        logger.debug(message)