import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from config import config


def setup_logger(name: str = __name__) -> logging.Logger:
    """
    Setup and configure logger with console and file handlers.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Create log directory if it doesn't exist
    config.logging.log_dir.mkdir(parents=True, exist_ok=True)

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.logging.log_level_console))
    console_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)

    # File handler (DEBUG and above) with rotation
    log_file = config.logging.log_dir / config.logging.log_file
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=config.logging.rotation_days
    )
    file_handler.setLevel(getattr(logging, config.logging.log_level_file))
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# Create default logger
logger = setup_logger('fpl_analytics')
