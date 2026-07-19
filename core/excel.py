"""
core/excel.py
==============
Reads the input workbook and appends to the failures CSV.

The real sheet (grouped_invoices_by_template_1807.xlsx, 62,440 rows) has
two columns:
    Grouped_Invoice_Numbers  - comma-separated invoice numbers to search
                               for together, e.g.
                               "251000169511, 251000023518, 25200087"
                               (usually 5 per row, but the parser makes no
                               assumption about group size - 1, 3, and 4
                               all occur in the real data too)
    Print_Template           - which "Print template" dropdown option to
                               select before downloading

Column names are configurable in config.py in case the sheet's headers
ever change.
"""
from __future__ import annotations

import csv
import logging
import os
from typing import List, NamedTuple

import pandas as pd

from config import settings

logger = logging.getLogger("invoice_automation")


class InvoiceRow(NamedTuple):
    excel_row: int                       # 0-based position within the DataFrame (used for resume)
    expected_invoice_numbers: List[str]  # parsed from Grouped_Invoice_Numbers
    print_template: str


def display_row(excel_row: int) -> int:
    """
    Convert a 0-based DataFrame index into the row number you'd actually
    see if you opened the sheet in Excel (row 1 is the header, data starts
    at row 2). Used everywhere we log or report a row to a human.
    """
    return excel_row + 2


def _clean_cell(value: object) -> str:
    """
    Safely stringify a cell value.

    Even with dtype=str, pandas represents a genuinely empty cell as NaN
    (a float), and `str(float('nan'))` is the literal text ``'nan'`` - which
    would otherwise be treated as real input. This normalises a blank/NaN
    cell to an empty string instead.
    """
    if pd.isna(value):
        return ""
    return str(value).strip()


def parse_invoice_numbers(raw_cell: str) -> List[str]:
    """
    Split a Grouped_Invoice_Numbers cell into individual invoice numbers.

    Handles the delimiter configured in settings.INVOICE_NUMBER_DELIMITER
    (a comma, matching the sheet and the site's own search box), strips
    whitespace around each number, and drops any empty fragments that a
    stray trailing delimiter would otherwise produce.
    """
    if not raw_cell:
        return []
    parts = raw_cell.split(settings.INVOICE_NUMBER_DELIMITER)
    return [p.strip() for p in parts if p.strip()]


def read_rows(path: str = settings.EXCEL_FILE) -> List[InvoiceRow]:
    """
    Load the workbook and return a list of InvoiceRow.

    Both columns are read as strings (`dtype=str`) deliberately: pandas
    will silently turn a numeric-looking column into float64 (adding a
    trailing ``.0`` to every value) the moment a blank cell introduces a
    NaN anywhere in that column, which would corrupt invoice-number
    comparisons against the site's search results. Reading as string and
    cleaning via `_clean_cell` avoids that entirely.
    """
    df = pd.read_excel(
        path,
        dtype={settings.COL_GROUPED_INVOICE_NUMBERS: str, settings.COL_PRINT_TEMPLATE: str},
    )

    missing_cols = {settings.COL_GROUPED_INVOICE_NUMBERS, settings.COL_PRINT_TEMPLATE} - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"Input Excel is missing expected column(s): {sorted(missing_cols)}. "
            f"Found columns: {list(df.columns)}"
        )

    rows: List[InvoiceRow] = []
    for idx, record in df.iterrows():
        raw_numbers = _clean_cell(record[settings.COL_GROUPED_INVOICE_NUMBERS])
        template = _clean_cell(record[settings.COL_PRINT_TEMPLATE])
        rows.append(
            InvoiceRow(
                excel_row=int(idx),
                expected_invoice_numbers=parse_invoice_numbers(raw_numbers),
                print_template=template,
            )
        )

    logger.info("Loaded %d rows from %s", len(rows), path)
    return rows


def init_failures_file(path: str = settings.FAILURES_FILE) -> None:
    """Create failures.csv with a header if it doesn't already exist."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["ExcelRow", "MissingInvoice", "PrintTemplate"])


def append_failure(
    excel_row_display: int,
    missing_invoice: str,
    print_template: str,
    path: str = settings.FAILURES_FILE,
) -> None:
    """
    Append a single missing invoice - one row per missing invoice number,
    never just the grouped string, per the spec.

    Opened and closed per call, on purpose: this keeps the CSV safe against
    the process being killed mid-run - nothing is buffered in memory that
    could be lost.
    """
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([excel_row_display, missing_invoice, print_template])
