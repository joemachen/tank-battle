"""
game/utils/logger.py

Single configuration point for all logging in the application.
Every module obtains its logger via get_logger(__name__).

Usage:
    from game.utils.logger import get_logger
    log = get_logger(__name__)
    log.info("System initialized")
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from game.utils.constants import LOG_FILE, LOGS_DIR

_configured: bool = False


def _configure_logging(dev_mode: bool = True) -> None:
    """Configure the root logger. Called once at application startup."""
    global _configured
    if _configured:
        return

    os.makedirs(LOGS_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Rotating file handler — 10 MB per file, keep 3 backups
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    root.addHandler(file_handler)

    # Console handler — DEBUG in dev mode, WARNING in production
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if dev_mode else logging.WARNING)
    console_fmt = logging.Formatter(
        fmt="%(levelname)-8s %(name)s: %(message)s",
    )
    console_handler.setFormatter(console_fmt)
    root.addHandler(console_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger. Ensures logging is configured before returning.
    Always pass __name__ as the argument.
    """
    if not _configured:
        _configure_logging()
    return logging.getLogger(name)


def configure(dev_mode: bool = True) -> None:
    """
    Explicitly configure logging at application startup.
    Call this once from main.py before anything else.
    """
    _configure_logging(dev_mode=dev_mode)
