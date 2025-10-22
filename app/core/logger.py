import logging
import sys
from logging import Logger


def get_logger(name: str = "app") -> Logger:
    """
    Logger ساده با فرمت یکدست برای کل سرویس.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
