"""
config.py
==========
Central configuration. Edit this file (or set the matching environment
variable) to adapt the automation to a different machine, a different
Excel layout, or a different pace of execution. Every other module reads
its settings from here - nothing else in the codebase hard-codes a path,
timeout, or column name.
"""
from __future__ import annotations

import os


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    return default if val is None else val.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val else default


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default)


class settings:  # noqa: N801 - used as a plain namespace, never instantiated
    # ------------------------------------------------------------------ #
    # Chrome attach settings
    # ------------------------------------------------------------------ #
    # This automation NEVER performs login. It attaches Selenium to a
    # Chrome window that a human has already opened and signed in to,
    # via Chrome's remote-debugging protocol. See README.md for the
    # one-time manual launch command.
    CHROME_DEBUGGER_ADDRESS = _str("CHROME_DEBUGGER_ADDRESS", "127.0.0.1:9222")

    # If True, driver.quit() is called when the script finishes normally
    # or is interrupted. Keep this False (default) if the attached Chrome
    # window is a session you want to keep open/inspect afterwards.
    CLOSE_BROWSER_ON_EXIT = _bool("CLOSE_BROWSER_ON_EXIT", False)

    # ------------------------------------------------------------------ #
    # Site
    # ------------------------------------------------------------------ #
    ARCHIVE_URL = _str(
        "ARCHIVE_URL", "https://app.sa.cleartax.com/new-einvoicing/archive"
    )

    # ------------------------------------------------------------------ #
    # Input / output paths
    # ------------------------------------------------------------------ #
    # The real input sheet lives in input/ inside this project for easy
    # reference - drop a replacement file with the same name here, or
    # point EXCEL_FILE (or the env var of the same name) at a different path.
    EXCEL_FILE = _str(
        "EXCEL_FILE", os.path.join("input", "grouped_invoices_by_template_1807.xlsx")
    )
    DOWNLOAD_FOLDER = _str(
        "DOWNLOAD_FOLDER",
        r"C:\Users\LENOVO\OneDrive - Samara Trading & Contracting Co\Invoices",
    )
    LOG_DIR = _str("LOG_DIR", "logs")
    OUTPUT_DIR = _str("OUTPUT_DIR", "output")
    PROGRESS_FILE = _str("PROGRESS_FILE", os.path.join(OUTPUT_DIR, "progress.json"))
    FAILURES_FILE = _str("FAILURES_FILE", os.path.join(OUTPUT_DIR, "failures.csv"))
    AUTOMATION_LOG = _str("AUTOMATION_LOG", os.path.join(LOG_DIR, "automation.log"))

    # ------------------------------------------------------------------ #
    # Excel column names - change here if the real sheet's headers differ
    # ------------------------------------------------------------------ #
    # Sheet layout (confirmed against grouped_invoices_by_template_1807.xlsx,
    # 62,440 rows):
    #   Grouped_Invoice_Numbers  - comma-separated invoice numbers, e.g.
    #                              "251000169511, 251000023518, 25200087"
    #                              (mostly 5 per row, but 1/3/4 also occur -
    #                              the parser handles any group size)
    #   Print_Template           - one of the exact dropdown option labels,
    #                              e.g. TAX_SAMARA_COBRA, SIMPLIFIED_SAMARA,
    #                              TAX_SAMARA_ARAMCO, TAX_SAMARA, TAX_SAMARA_JHAH
    COL_GROUPED_INVOICE_NUMBERS = _str("COL_GROUPED_INVOICE_NUMBERS", "Grouped_Invoice_Numbers")
    COL_PRINT_TEMPLATE = _str("COL_PRINT_TEMPLATE", "Print_Template")

    # Delimiter used to both split the sheet's Grouped_Invoice_Numbers cell
    # and to re-join the numbers when typing them into the search box.
    INVOICE_NUMBER_DELIMITER = ","

    # ------------------------------------------------------------------ #
    # Timeouts (seconds)
    # ------------------------------------------------------------------ #
    # Tuned down from more conservative defaults: a normal, successful
    # interaction on this page completes in 1-2 seconds, so these mostly
    # matter for how long a GENUINELY stuck row waits before giving up and
    # moving on. Raise them back up if your network/site is consistently
    # slower than that.
    WAIT_TIMEOUT = _int("WAIT_TIMEOUT", 12)                    # generic explicit wait
    SEARCH_RESULT_TIMEOUT = _int("SEARCH_RESULT_TIMEOUT", 20)  # waiting for the banner
    DOWNLOAD_TIMEOUT = _int("DOWNLOAD_TIMEOUT", 90)            # waiting for the PDF
    DROPDOWN_TIMEOUT = _int("DROPDOWN_TIMEOUT", 8)             # opening/filtering menus

    # ------------------------------------------------------------------ #
    # Retry behaviour (see core/retry.py)
    # ------------------------------------------------------------------ #
    RETRY_ATTEMPTS = _int("RETRY_ATTEMPTS", 3)
    RETRY_BACKOFF_SECONDS = float(_int("RETRY_BACKOFF_SECONDS", 1))

    # ------------------------------------------------------------------ #
    # Long-run stability
    # ------------------------------------------------------------------ #
    CHECKPOINT_INTERVAL = _int("CHECKPOINT_INTERVAL", 25)    # rows between progress.json saves
    REFRESH_AFTER_ROWS = _int("REFRESH_AFTER_ROWS", 500)     # rows between page refreshes

    # Document type is always forced to PDF regardless of the sheet content
    # (per the workflow: PDF must always be selected before Download).
    DOCUMENT_TYPE = "PDF"
