"""
Logging utility for LCSC Manager plugin
"""
import logging
import logging.handlers
import os
from pathlib import Path

BASE = "lcsc_manager"
# The log used to grow without limit, at debug level. Now: this much, plus
# two older files (lcsc_manager.log.1, .2).
MAX_BYTES = 1024 * 1024
BACKUPS = 2

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


class _QuietRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotation that never gets in the plugin's way. On Windows the rename
    fails while another process (a second KiCad, the IPC plugin) has the
    log open; keep writing to the current file instead of raising on every
    record."""

    def doRollover(self):
        try:
            super().doRollover()
        except OSError:
            if self.stream is None:
                self.stream = self._open()


def setup_logger(name: str = BASE) -> logging.Logger:
    """
    Setup and configure the plugin's logger. All other loggers are its
    children, so there is one file handler (and one open file) however many
    modules log.

    Args:
        name: Logger name (kept for compatibility; the base logger is
            always the one configured)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(BASE)

    # Only setup if not already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    # KiCad or another plugin may have set up the root logger; don't let
    # our records show up there a second time.
    logger.propagate = False

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler. A home folder that can't be written to (read-only,
    # sandboxed) must not stop the plugin from loading.
    try:
        path = log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = _QuietRotatingFileHandler(
            path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.addHandler(logging.NullHandler())

    # Console handler
    if _console_logging:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        _console_handlers.append((logger, console_handler))

    return logger


def get_logger(name: str = BASE) -> logging.Logger:
    """
    Get logger instance

    Args:
        name: Logger name; anything but the base name becomes a child of
            the base logger ("lcsc_manager.<name>")

    Returns:
        Logger instance
    """
    base = setup_logger()
    if name == BASE or not name:
        return base
    return base.getChild(name[len(BASE) + 1:] if name.startswith(BASE + ".") else name)
