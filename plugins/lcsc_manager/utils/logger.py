"""
Logging utility for LCSC Manager plugin
"""
import logging
import os
from pathlib import Path


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
    log_dir = Path.home() / ".kicad" / "lcsc_manager" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # File handler
    log_file = log_dir / "lcsc_manager.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

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
