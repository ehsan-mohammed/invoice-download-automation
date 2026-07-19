"""
core/browser.py
================
Attaches Selenium to an ALREADY RUNNING Chrome instance via the DevTools
remote-debugging protocol. This automation never logs in, never touches
credentials, and never launches a fresh browser of its own - it only
reuses a Chrome window that a human has already signed in to.

One-time manual setup (see README.md for the full walkthrough): start
Chrome with a dedicated automation profile and a debugging port, e.g.

    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" ^
        --remote-debugging-port=9222 ^
        --user-data-dir="C:\\ChromeAutomation"

...then sign in to ClearTax by hand in that window before starting main.py.
"""
from __future__ import annotations

import logging
import subprocess
import sys

from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from urllib3.exceptions import MaxRetryError, NewConnectionError, ProtocolError
from webdriver_manager.chrome import ChromeDriverManager

from config import settings

logger = logging.getLogger("invoice_automation")

# ---------------------------------------------------------------------- #
# Exceptions that mean "the browser/automation session itself is broken",
# as opposed to a normal per-row problem (a slow dropdown, an element that
# needed a retry, an invoice that genuinely wasn't found, etc.). main.py
# treats these two categories very differently: a session-fatal error must
# NOT be logged as if the row's invoices were "not found" (that would
# write false failures to failures.csv), and must NOT advance progress
# past that row (or it would never be retried).
#
# IMPORTANT: this deliberately does NOT include the general-purpose
# selenium.common.exceptions.WebDriverException. Almost every ordinary
# Selenium error (TimeoutException, ElementClickInterceptedException,
# StaleElementReferenceException, NoSuchElementException, ...) is ALSO a
# WebDriverException under the hood, so including it here would swallow
# up completely normal, already-retried, single-row failures and treat
# them as if the whole browser had died - which is exactly the bug that
# caused a slow print-template dropdown to abort an entire 62,440-row run.
# Only the two narrow "the session is truly gone" cases are included
# below, alongside the transport-level exceptions that fire when the HTTP
# connection to chromedriver itself is severed (e.g. it got killed).
# ---------------------------------------------------------------------- #
SESSION_FATAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    InvalidSessionIdException,  # the browser session was closed/invalidated
    NoSuchWindowException,      # the Chrome window itself was closed
    ConnectionError,            # built-in; covers ConnectionResetError/ConnectionAbortedError
    OSError,                    # broader socket-level failures
    ProtocolError,              # urllib3 - what Selenium's HTTP client raises on a reset socket
    MaxRetryError,              # urllib3 - retries to chromedriver's local port exhausted
    NewConnectionError,         # urllib3 - couldn't even open a new connection
)


def attach_to_running_chrome() -> webdriver.Chrome:
    """
    Return a WebDriver bound to the Chrome instance listening on
    ``settings.CHROME_DEBUGGER_ADDRESS``.

    Note: even in "attach" mode, Selenium still needs a local chromedriver
    binary that matches the running Chrome's version to relay commands -
    it just won't launch a *new* browser window because debuggerAddress is
    set. webdriver-manager downloads/caches the right binary automatically.

    On Windows, chromedriver.exe is started with CREATE_NEW_PROCESS_GROUP.
    Without this, pressing Ctrl+C in the terminal sends that signal to
    EVERY process sharing the console - including chromedriver.exe - which
    kills it mid-request and surfaces as a confusing
    "Connection aborted ... forcibly closed by the remote host" error
    instead of a clean shutdown. Isolating it into its own process group
    means Ctrl+C only reaches this script, exactly as intended.

    Raises
    ------
    selenium.common.exceptions.WebDriverException
        If no Chrome instance is listening on that debugger address - the
        most common cause is forgetting the one-time manual launch step
        above before running this script.
    """
    options = Options()
    options.add_experimental_option("debuggerAddress", settings.CHROME_DEBUGGER_ADDRESS)

    popen_kw = {}
    if sys.platform == "win32":
        popen_kw["creation_flags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    service = Service(ChromeDriverManager().install(), popen_kw=popen_kw)

    logger.info(
        "Attaching Selenium to existing Chrome session at %s",
        settings.CHROME_DEBUGGER_ADDRESS,
    )
    driver = webdriver.Chrome(service=service, options=options)
    logger.info("Attached successfully. Current URL: %s", driver.current_url)
    return driver


def ensure_on_archive_page(driver: webdriver.Chrome) -> None:
    """Navigate to the archive page only if we are not already there."""
    if settings.ARCHIVE_URL not in driver.current_url:
        logger.info("Navigating to %s", settings.ARCHIVE_URL)
        driver.get(settings.ARCHIVE_URL)
