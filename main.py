"""
main.py
========
Entry point. Reads the Excel sheet and drives the browser row by row:

    1. Join that row's Grouped_Invoice_Numbers with a comma and paste them
       into the search box, click "Search Documents".
    2. Read back what the site actually found - never trusting the "N
       found" count alone, the individual returned invoice numbers are
       always parsed and compared against what was expected.
    3. Every expected invoice number NOT returned by the site is logged
       to failures.csv individually (never just the grouped string).
    4. If AT LEAST ONE expected invoice was found, proceed anyway: force
       "PDF", pick the row's Print_Template, click Download, and wait for
       the file to actually finish downloading. A row is only skipped
       entirely if the site found none of its expected invoices.
    5. Move to the next row.

Run:
    python main.py

Resume after a stop/crash:
    Just run it again - core/progress.py picks up right after the last
    row that fully completed.

Stop safely:
    Ctrl+C at any time. The current row finishes (or is abandoned safely),
    progress is saved immediately, and the browser is left open.
"""
from __future__ import annotations

import logging
import signal
import sys
from types import FrameType
from typing import Optional

from tqdm import tqdm

from config import settings
from core.browser import SESSION_FATAL_EXCEPTIONS, attach_to_running_chrome, ensure_on_archive_page
from core.comparator import compare
from core.downloader import snapshot_folder, wait_for_new_download
from core.excel import InvoiceRow, append_failure, display_row, init_failures_file, read_rows
from core.logger import log_row, setup_logging
from core.progress import Progress, load_progress, save_progress
from pages.archive_page import ArchivePage

logger = logging.getLogger("invoice_automation")

_shutdown_requested = False


def _handle_sigint(signum: int, frame: Optional[FrameType]) -> None:
    global _shutdown_requested
    logger.warning("Ctrl+C received - finishing the current row, then stopping safely.")
    _shutdown_requested = True


def process_row(page: ArchivePage, row: InvoiceRow) -> None:
    """Run one Excel row end to end. Any exception raised here is caught
    by the caller (main loop) so one bad row can never kill a 60k-row run."""
    disp_row = display_row(row.excel_row)

    if not row.expected_invoice_numbers:
        log_row(logger, disp_row, "Skipped - no invoice numbers parsed from this row.")
        return

    search_text = settings.INVOICE_NUMBER_DELIMITER.join(row.expected_invoice_numbers)
    log_row(
        logger, disp_row,
        f"Searching {len(row.expected_invoice_numbers)} invoice(s): {search_text}",
    )

    page.reset_search_form()
    page.search(search_text)
    result = page.get_search_result()

    # Step 6-7: never trust the count alone - compare the actual returned
    # invoice numbers against what this row expected.
    comparison = compare(row.expected_invoice_numbers, result.found_numbers)

    log_row(
        logger, disp_row,
        f"Expected={len(comparison.expected)} Found={result.found_count} "
        f"Missing={len(comparison.missing)}",
    )

    # Step 8: log every missing invoice individually - never just the
    # grouped string.
    for missing_invoice in comparison.missing:
        append_failure(disp_row, missing_invoice, row.print_template)

    # Step 9: only skip the download if NONE of the expected invoices
    # were found. Even 1-of-5 found still means we download that one.
    if not comparison.any_found:
        log_row(logger, disp_row, "None of the expected invoices were found - skipping download.")
        return

    if comparison.missing:
        log_row(
            logger, disp_row,
            f"Proceeding to download the {comparison.found_count_of_expected} "
            f"invoice(s) that were found; {len(comparison.missing)} logged as missing.",
        )

    # Step 10-11: format is always PDF, template comes from the sheet.
    # Each step is logged right BEFORE it runs (not just after success) so
    # that if something throws, automation.log's last line for this row
    # tells you exactly which step it was in - not just that "something"
    # failed.
    log_row(logger, disp_row, "Selecting PDF format...")
    page.select_pdf_format()

    log_row(logger, disp_row, f"Selecting print template '{row.print_template}'...")
    page.select_print_template(row.print_template)

    # Step 12-13: download, then actually wait for the file to land.
    before_files = snapshot_folder()
    log_row(logger, disp_row, "Clicking Download button...")
    page.click_download()

    log_row(logger, disp_row, "Waiting for the PDF download to complete...")
    try:
        finished_file = wait_for_new_download(before_files)
        log_row(logger, disp_row, f"Completed - downloaded: {finished_file}")
    except TimeoutError as exc:
        log_row(logger, disp_row, f"Download FAILED: {exc}")
        # The download itself never completed, so none of the invoices we
        # thought we'd get can be confirmed as saved. Conservatively log
        # every invoice that WAS found (and therefore wasn't already
        # logged as missing above) as a failure too.
        for invoice_number in row.expected_invoice_numbers:
            if invoice_number not in comparison.missing:
                append_failure(disp_row, invoice_number, row.print_template)


def main() -> int:
    setup_logging()
    init_failures_file()
    signal.signal(signal.SIGINT, _handle_sigint)

    rows = read_rows()
    progress: Progress = load_progress()
    start_index = progress.last_completed_row + 1

    if start_index >= len(rows):
        logger.info("Nothing to do - all %d rows already completed.", len(rows))
        return 0

    logger.info("Resuming from row %d of %d (0-based index).", start_index, len(rows))

    driver = attach_to_running_chrome()
    ensure_on_archive_page(driver)
    page = ArchivePage(driver)
    page.open()

    rows_since_checkpoint = 0
    rows_since_refresh = 0

    try:
        for row in tqdm(rows[start_index:], initial=start_index, total=len(rows), unit="row"):
            if _shutdown_requested:
                logger.warning("Stopping before row %d due to Ctrl+C.", display_row(row.excel_row))
                break

            try:
                process_row(page, row)
            except SESSION_FATAL_EXCEPTIONS as exc:
                # The browser/chromedriver connection itself broke (crashed,
                # got killed, network blip, etc.) - this tells us NOTHING
                # about whether this row's invoices exist. Do NOT log them
                # as missing, and do NOT advance progress past this row, or
                # it would be silently skipped forever. Stop the whole run
                # instead: re-running main.py resumes from this exact row
                # once the browser session is healthy again.
                logger.error(
                    "Row %d: browser/session connection failed (%s: %s). "
                    "Stopping the run WITHOUT marking this row complete and "
                    "WITHOUT logging its invoices as missing - this looks "
                    "like an infrastructure hiccup, not a genuine 'not "
                    "found' result. Make sure Chrome/chromedriver is still "
                    "running and re-run main.py - it will resume from "
                    "exactly this row.",
                    display_row(row.excel_row), type(exc).__name__, exc,
                )
                break
            except Exception as exc:  # noqa: BLE001 - one bad row must never kill 60k rows
                logger.exception(
                    "Row %d: FAILED after exhausting retries (%s: %s). Every "
                    "invoice in this row's group is being logged to "
                    "failures.csv as a precaution, and the run continues "
                    "with the next row. (See the 'Row %d | ...' lines just "
                    "above this for exactly which step - search, format, "
                    "template, or download - was in progress.)",
                    display_row(row.excel_row), type(exc).__name__, exc,
                    display_row(row.excel_row),
                )
                for invoice_number in row.expected_invoice_numbers:
                    append_failure(display_row(row.excel_row), invoice_number, row.print_template)

                # A row-level failure often means the PAGE got stuck (e.g. a
                # button that stays disabled no matter how long we wait),
                # not just a one-off blip - and a stuck page won't fix
                # itself. Refreshing right away, instead of waiting for the
                # periodic REFRESH_AFTER_ROWS refresh, stops a single stuck
                # page from silently failing every row after it too.
                try:
                    logger.info("Refreshing the page after this failure, to clear any stuck state.")
                    page.refresh()
                except SESSION_FATAL_EXCEPTIONS as refresh_exc:
                    logger.error(
                        "Row %d: the recovery refresh itself hit a session-fatal "
                        "error (%s: %s). This row's failure above is still valid "
                        "and stays logged - stopping the run here so you can "
                        "check the browser/session before re-running main.py.",
                        display_row(row.excel_row), type(refresh_exc).__name__, refresh_exc,
                    )
                    progress.last_completed_row = row.excel_row
                    save_progress(progress)
                    break

            progress.last_completed_row = row.excel_row
            rows_since_checkpoint += 1
            rows_since_refresh += 1

            if rows_since_checkpoint >= settings.CHECKPOINT_INTERVAL:
                save_progress(progress)
                rows_since_checkpoint = 0

            if rows_since_refresh >= settings.REFRESH_AFTER_ROWS:
                page.refresh()
                rows_since_refresh = 0

    finally:
        save_progress(progress)
        logger.info("Progress saved at row %d.", progress.last_completed_row)
        if settings.CLOSE_BROWSER_ON_EXIT:
            try:
                driver.quit()
            except Exception:  # noqa: BLE001 - the session may already be dead; don't mask the real error
                logger.warning("driver.quit() failed - the browser session was likely already gone.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
