"""
core/logger.py
================
Configures:
    1. A single console+file logger (`invoice_automation`), writing to
       logs/automation.log, used everywhere else in the codebase.
    2. `log_row`, a tiny helper that prefixes every row-level event with
       its Excel row number, so automation.log reads as a clean, greppable
       audit trail across a multi-hour, 60k-row run.
"""
from __future__ import annotations

import logging
import os

from config import settings


def setup_logging() -> logging.Logger:
    os.makedirs(settings.LOG_DIR, exist_ok=True)

    logger = logging.getLogger("invoice_automation")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        # Already configured in this process - avoid duplicate handlers
        # (e.g. if setup_logging() is called more than once).
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(settings.AUTOMATION_LOG, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger


def log_row(logger: logging.Logger, row: int, message: str) -> None:
    """Uniform 'Row N | message' line, e.g.:
        2026-07-18 09:10:03 | INFO    | Row 245 | Searching TRX=241000051480
    """
    logger.info("Row %s | %s", row, message)
