"""
core/retry.py
==============
A small retry decorator for the specific transient Selenium exceptions
that show up in long-running automations against a React/MUI app:
elements re-rendering mid-interaction (stale references), overlays briefly
intercepting a click, and slow XHRs tripping an explicit wait.

Note on the backoff sleep below: this is a bounded pause between RETRIES of
an already-failed operation, not a substitute for an explicit DOM wait -
those still happen via core/waits.py inside the wrapped function itself.
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Callable, Optional, Tuple, Type, TypeVar

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)

from config import settings

logger = logging.getLogger("invoice_automation")

T = TypeVar("T")

DEFAULT_RETRY_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)


def retry_on_flaky_ui(
    attempts: int = settings.RETRY_ATTEMPTS,
    backoff_seconds: float = settings.RETRY_BACKOFF_SECONDS,
    exceptions: Tuple[Type[BaseException], ...] = DEFAULT_RETRY_EXCEPTIONS,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry a function up to `attempts` times if it raises one of the given
    Selenium exceptions, with a linearly increasing backoff between tries.
    Re-raises the last exception if every attempt fails.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Optional[BaseException] = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    logger.warning(
                        "%s failed on attempt %d/%d (%s: %s). Retrying...",
                        func.__name__, attempt, attempts, type(exc).__name__, exc,
                    )
                    if attempt < attempts:
                        time.sleep(backoff_seconds * attempt)
            logger.error("%s failed after %d attempts. Giving up.", func.__name__, attempts)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
