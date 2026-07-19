"""
core/comparator.py
====================
Pure, browser-free logic for comparing "what we searched for" against
"what the site actually returned" (Steps 6-9 of the workflow). Kept
separate from ArchivePage/main.py so it's trivially unit-testable without
Selenium or a live site.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class ComparisonResult:
    expected: List[str]
    found: List[str]
    missing: List[str]

    @property
    def found_count_of_expected(self) -> int:
        """How many of the numbers we searched for were actually returned."""
        return len(self.expected) - len(self.missing)

    @property
    def any_found(self) -> bool:
        """
        True if at least one of the expected invoices was actually
        returned by the search. This decides whether to still proceed to
        download (Step 9: "if at least one invoice exists, continue - do
        NOT abort because some invoices are missing").
        """
        return self.found_count_of_expected > 0


def compare(expected: List[str], found: List[str]) -> ComparisonResult:
    """
    Compare the invoice numbers we searched for against the ones the site
    returned.

    `missing` preserves the original order of `expected` and includes
    every expected number that is NOT present in `found`. The site's
    returned count is never trusted on its own (Step 6: "do NOT trust the
    count") - this always compares the actual returned numbers.
    """
    found_set = set(found)
    missing = [num for num in expected if num not in found_set]
    return ComparisonResult(expected=expected, found=found, missing=missing)
