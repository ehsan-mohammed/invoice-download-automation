"""
core/waits.py
==============
Thin, well-documented wrappers around Selenium's WebDriverWait so the rest
of the codebase never needs a bare `time.sleep()` to wait for the DOM.
"""
from __future__ import annotations

from typing import Tuple

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

Locator = Tuple[str, str]


def wait_visible(driver: WebDriver, locator: Locator, timeout: int) -> WebElement:
    """Wait until the element is present AND visible (not display:none)."""
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))


def wait_clickable(driver: WebDriver, locator: Locator, timeout: int) -> WebElement:
    """Wait until the element is visible and enabled for interaction."""
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))


def wait_present(driver: WebDriver, locator: Locator, timeout: int) -> WebElement:
    """Wait until the element exists in the DOM (it may still be hidden)."""
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))


def wait_all_present(driver: WebDriver, locator: Locator, timeout: int):
    """Wait until at least one matching element exists, return all matches."""
    return WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located(locator))


def wait_clickable_last(driver: WebDriver, locator: Locator, timeout: int, poll_frequency: float = 0.3) -> WebElement:
    """
    Like wait_clickable, but tolerant of stale/duplicate copies of an
    element lingering in the DOM.

    Some React/MUI components don't cleanly unmount their previous render
    before mounting the next one, so a locator that matched a single
    button on the first search can start matching TWO (an old, hidden/
    dead copy plus the live one) on later searches. Selenium's built-in
    element_to_be_clickable() always resolves to the FIRST DOM match,
    which - once a stale copy exists - can be the dead one, causing a
    genuine, permanent timeout even though a perfectly clickable live
    copy is sitting right next to it.

    This waits until AT LEAST ONE match is genuinely displayed and
    enabled, then returns the LAST such match, on the assumption that
    newly-rendered content is appended after older, stale content.
    """

    def _find_last_clickable(drv: WebDriver):
        elements = drv.find_elements(*locator)
        clickable = [e for e in elements if e.is_displayed() and e.is_enabled()]
        return clickable[-1] if clickable else False

    return WebDriverWait(driver, timeout, poll_frequency=poll_frequency).until(_find_last_clickable)
