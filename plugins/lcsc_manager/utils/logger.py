"""
Logging utility for LCSC Manager plugin
"""
import logging
import os
from pathlib import Path

# Console handlers write to stderr. The IPC entry point turns them off, since
# it points stderr at the log file itself (see ipc_main.py).
_console_logging = True
_console_handlers = []


def log_file() -> Path:
    """The file every logger writes to."""
    return Path.home() / ".kicad" / "lcsc_manager" / "logs" / "lcsc_manager.log"


def log_to_file_only() -> None:
    """Stop logging to the console, for loggers set up so far and later."""
    global _console_logging
    _console_logging = False
    for logger, handler in _console_handlers:
        logger.removeHandler(handler)
    _console_handlers.clear()


def setup_logger(name: str = "lcsc_manager") -> logging.Logger:
    """
    Setup and configure logger for the plugin

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only setup if not already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Create logs directory in user's home
    path = log_file()
    path.parent.mkdir(parents=True, exist_ok=True)

    # File handler
    file_handler = logging.FileHandler(path)
    file_handler.setLevel(logging.DEBUG)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    if _console_logging:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        _console_handlers.append((logger, console_handler))

    return logger


def get_logger(name: str = "lcsc_manager") -> logging.Logger:
    """
    Get logger instance

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger
