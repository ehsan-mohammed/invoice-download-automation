"""
pages/archive_page.py
=======================
Page Object for the ClearTax "Archives -> Search invoices" tab.

Every raw locator lives in locators.py; this class only orchestrates the
user-visible workflow described in the automation spec: search -> read
result -> force PDF format -> pick template -> download.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List

from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver

import locators as L
from config import settings
from core.retry import retry_on_flaky_ui
from core.waits import wait_clickable_last, wait_present, wait_visible

logger = logging.getLogger("invoice_automation")

_COUNT_PATTERN = re.compile(r"(\d+)\s+E-invoices found", re.IGNORECASE)


@dataclass
class SearchResult:
    found_count: int                       # N, parsed from the banner text
    found_numbers: List[str] = field(default_factory=list)  # the actual numbers returned


class ArchivePage:
    """Encapsulates all Selenium interaction with the Archives search page."""

    def __init__(self, driver: WebDriver) -> None:
        self.driver = driver

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def open(self) -> None:
        if settings.ARCHIVE_URL not in self.driver.current_url:
            self.driver.get(settings.ARCHIVE_URL)
        self._ensure_search_tab_active()
        wait_present(self.driver, L.SEARCH_INPUT, settings.WAIT_TIMEOUT)

    def refresh(self) -> None:
        """Used for long-run stability - React apps can accumulate memory/
        state drift over many hours; refreshing periodically resets that."""
        logger.info("Refreshing page for long-run stability.")
        self.driver.refresh()
        self._ensure_search_tab_active()
        wait_present(self.driver, L.SEARCH_INPUT, settings.WAIT_TIMEOUT)

    def _ensure_search_tab_active(self) -> None:
        """
        Loading the archive URL - or refreshing it - lands on the
        "Generate reports" tab by default, not "Search invoices". None of
        this automation's locators exist on that tab, so every page
        load/reload must click back onto "Search invoices" before doing
        anything else. Harmless (and near-instant) if that tab is already
        selected.
        """
        try:
            tab = wait_clickable_last(self.driver, L.SEARCH_INVOICES_TAB, settings.WAIT_TIMEOUT)
            tab.click()
        except TimeoutException:
            logger.warning(
                "Could not find/click the 'Search invoices' tab - "
                "continuing anyway in case it's already active."
            )

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    @retry_on_flaky_ui()
    def reset_search_form(self) -> None:
        """
        Click 'Start again' if it's actually clickable right now.

        This is a harmless no-op whenever it isn't - most commonly on the
        very first search of a session (nothing to reset yet, so the
        button renders in a disabled style and intercepts its own click),
        but also possibly mid-transition between two rows. Skipping it
        costs nothing: search() clears the search box itself before
        typing, and a fresh search naturally replaces whatever the
        previous result banner showed.
        """
        try:
            btn = wait_clickable_last(self.driver, L.START_AGAIN_BUTTON, 3)
            btn.click()
        except (TimeoutException, ElementClickInterceptedException):
            pass  # nothing to reset, or it's currently disabled - both fine

    @retry_on_flaky_ui()
    def search(self, search_text: str) -> None:
        """`search_text` is the exact string typed into the search box -
        for this workflow, the row's invoice numbers already joined with
        the configured delimiter (see main.py)."""
        box = wait_visible(self.driver, L.SEARCH_INPUT, settings.WAIT_TIMEOUT)
        box.clear()
        box.send_keys(search_text)
        button = wait_clickable_last(self.driver, L.SEARCH_BUTTON, settings.WAIT_TIMEOUT)
        button.click()

    def get_search_result(self) -> SearchResult:
        """
        Wait for the result banner and parse it.

        Returns SearchResult(found_count=0) - WITHOUT raising - if the page
        never shows the "N E-invoices found..." text within the timeout.
        A zero-result search is an expected, valid outcome of this workflow
        (the row simply gets logged as missing), not an error condition.
        See the VERIFY_ON_NEXT_DEPLOY note in locators.py.
        """
        try:
            title_el = wait_present(self.driver, L.RESULT_TITLE, settings.SEARCH_RESULT_TIMEOUT)
        except TimeoutException:
            logger.warning(
                "Result banner text ('N E-invoices found...') did not appear "
                "within %ss - treating this search as zero results.",
                settings.SEARCH_RESULT_TIMEOUT,
            )
            return SearchResult(found_count=0)

        match = _COUNT_PATTERN.search(title_el.text)
        count = int(match.group(1)) if match else 0

        if count == 0:
            return SearchResult(found_count=0)

        # Invoice-number spans are DOM SIBLINGS of the title element (see
        # the comment block above locators.RESULT_TITLE for why this is
        # resilient to a hashed-CSS-class change on ClearTax's end).
        parent = title_el.find_element("xpath", "..")
        sibling_spans = parent.find_elements("xpath", "./span")
        found_numbers = [s.text.strip() for s in sibling_spans if s.text.strip().isdigit()]

        return SearchResult(found_count=count, found_numbers=found_numbers)

    # ------------------------------------------------------------------ #
    # Format + template selection
    # ------------------------------------------------------------------ #
    @retry_on_flaky_ui()
    def select_pdf_format(self) -> None:
        """
        Force the "PDF" radio on. XML is the site's default, and - this
        matters - the "Print template" dropdown only exists in the DOM
        once PDF is selected; it's not just hidden, it isn't rendered at
        all under XML. So if this click silently doesn't register, the
        very next step (select_print_template) has nothing to click and
        times out looking like an unrelated failure.

        To make this mandatory rather than "probably worked", this waits
        for the Print template control to actually appear after clicking,
        confirming the switch really took effect - not just that
        radio.is_selected() reports true on a reference that might be stale.
        """
        radio = wait_present(self.driver, L.PDF_RADIO_INPUT, settings.WAIT_TIMEOUT)
        if not radio.is_selected():
            # The native <input> sits under a custom-styled MUI overlay,
            # which can intercept a plain .click(). A JS click on the input
            # itself is the reliable way to toggle this kind of control.
            self.driver.execute_script("arguments[0].click();", radio)

        wait_present(self.driver, L.PRINT_TEMPLATE_HANDLE, settings.WAIT_TIMEOUT)

    @retry_on_flaky_ui()
    def select_print_template(self, template_name: str) -> None:
        handle = wait_clickable_last(self.driver, L.PRINT_TEMPLATE_HANDLE, settings.WAIT_TIMEOUT)
        handle.click()

        search_box = wait_visible(
            self.driver, L.PRINT_TEMPLATE_SEARCH_INPUT, settings.DROPDOWN_TIMEOUT
        )
        search_box.clear()
        search_box.send_keys(template_name)

        option_locator = (
            L.PRINT_TEMPLATE_OPTION_TEMPLATE[0],
            L.PRINT_TEMPLATE_OPTION_TEMPLATE[1].format(value=template_name),
        )
        try:
            option = wait_clickable_last(self.driver, option_locator, settings.DROPDOWN_TIMEOUT)
        except TimeoutException as exc:
            raise ValueError(
                f"Print template '{template_name}' was not found in the dropdown "
                f"options. Check for a typo in the Excel sheet, or confirm this "
                f"template exists for the currently active business."
            ) from exc
        option.click()

    # ------------------------------------------------------------------ #
    # Download
    # ------------------------------------------------------------------ #
    @retry_on_flaky_ui()
    def click_download(self) -> None:
        button = wait_clickable_last(self.driver, L.DOWNLOAD_BUTTON, settings.WAIT_TIMEOUT)
        button.click()
