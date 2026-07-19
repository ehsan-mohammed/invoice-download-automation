"""
core/downloader.py
====================
Detects PDF download completion by diffing the download folder's contents
before and after clicking "Download", and waiting until Chrome's
partial-download marker file (``*.crdownload``) is gone.

This is NOT a blind `time.sleep()` guess: it actively re-checks the folder
in a short bounded loop until either a genuinely new, complete file shows
up or DOWNLOAD_TIMEOUT is exceeded. Selenium's explicit waits have no
visibility into the OS-level download manager, so polling the filesystem
is the standard, necessary way to detect download completion with Chrome.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Set

from config import settings

logger = logging.getLogger("invoice_automation")

# Chrome (and some other browsers) name in-progress downloads with one of
# these suffixes until the file is fully written to disk.
CHROME_PARTIAL_SUFFIXES = (".crdownload", ".tmp")


def snapshot_folder(folder: str = settings.DOWNLOAD_FOLDER) -> Set[str]:
    """Return the current set of filenames in the download folder."""
    os.makedirs(folder, exist_ok=True)
    return set(os.listdir(folder))


def wait_for_new_download(
    before: Set[str],
    folder: str = settings.DOWNLOAD_FOLDER,
    timeout: int = settings.DOWNLOAD_TIMEOUT,
    poll_interval: float = 0.5,
) -> str:
    """
    Block until a new, fully-written file appears in `folder` that wasn't
    present in `before`, then return its filename.

    Raises
    ------
    TimeoutError
        If nothing new (and complete) appears within `timeout` seconds.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = set(os.listdir(folder))
        new_files = current - before

        still_downloading = [f for f in new_files if f.endswith(CHROME_PARTIAL_SUFFIXES)]
        complete_new_files = [f for f in new_files if not f.endswith(CHROME_PARTIAL_SUFFIXES)]

        if complete_new_files and not still_downloading:
            finished = complete_new_files[0]
            logger.debug("Detected completed download: %s", finished)
            return finished

        time.sleep(poll_interval)

    raise TimeoutError(
        f"No new completed download appeared in '{folder}' within {timeout}s"
    )
