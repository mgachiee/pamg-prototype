"""Lightweight logging wrapper for the PAMG system."""

import logging

logger = logging.getLogger(__name__)

class Logger:
    """
    Simple logger facade used across PAMG modules.

    This wrapper standardizes formatting and allows future expansion for
    multiple sinks (file, GUI, or external monitoring).
    """

    def __init__(self) -> None:
        """Configure logging defaults on first construction."""
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )

    def info(self, message: str) -> None:
        """
        Log an info-level message.

        Args:
            message (str): Message to log.
        """
        logger.info(message)

    def warning(self, message: str) -> None:
        """
        Log a warning-level message.

        Args:
            message (str): Message to log.
        """
        logger.warning(message)

    def error(self, message: str) -> None:
        """
        Log an error-level message.

        Args:
            message (str): Message to log.
        """
        logger.error(message)

    def debug(self, message: str) -> None:
        """
        Log a debug-level message.

        Args:
            message (str): Message to log.
        """
        logger.debug(message)