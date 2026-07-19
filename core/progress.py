"""
core/progress.py
==================
Resume support. Persists the last successfully completed Excel row index
to a small JSON file so a 60k-row run can be safely stopped (Ctrl+C, a
crash, a laptop sleep, etc.) and picked back up without redoing rows that
already finished.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass

from config import settings

logger = logging.getLogger("invoice_automation")


@dataclass
class Progress:
    # -1 means "nothing completed yet". Index is 0-based, matching the
    # DataFrame position used throughout core/excel.py.
    last_completed_row: int = -1


def load_progress() -> Progress:
    if not os.path.exists(settings.PROGRESS_FILE):
        return Progress()
    try:
        with open(settings.PROGRESS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return Progress(last_completed_row=int(data.get("last_completed_row", -1)))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning("Could not read %s (%s). Starting from row 0.", settings.PROGRESS_FILE, exc)
        return Progress()


def save_progress(progress: Progress) -> None:
    """Write atomically (write to a temp file, then rename) so a crash
    mid-write can never leave progress.json truncated/corrupted."""
    out_dir = os.path.dirname(settings.PROGRESS_FILE) or "."
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = settings.PROGRESS_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(asdict(progress), fh, indent=2)
    os.replace(tmp_path, settings.PROGRESS_FILE)  # atomic on Windows & POSIX
