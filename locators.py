"""
locators.py
============
All Selenium element locators for the ClearTax "Archives -> Search
invoices" page, extracted directly from a captured DOM snapshot of
https://app.sa.cleartax.com/new-einvoicing/archive

Design notes
------------
This page is a React/MUI application. Its CSS module class names carry a
build-specific hash suffix (e.g. ``_3-3-16``) that is very likely to change
the next time ClearTax ships a new frontend build. To keep this file
resilient to that, locators are built - in priority order - from:

    1. ``name`` attributes on form controls        -> very stable
    2. Visible button/label text                    -> stable unless UI copy changes
    3. DOM relationships (parent/sibling/position)   -> stable regardless of hashes
    4. Hashed CSS module classes                     -> only ever used as a
                                                         partial `contains()`
                                                         match, never as the
                                                         sole selector

If ClearTax ships a redesign and something here stops matching, this is the
ONLY file that should need to change - every page-object method reads its
locators from here rather than hard-coding XPaths inline.

VERIFY_ON_NEXT_DEPLOY
----------------------
The captured HTML only ever showed the ">=1 result" state of the search
banner (see the screenshot with "5 E-invoices found matching your search").
The "0 results" state was never captured, so its exact markup is unverified.
ArchivePage.get_search_result() is written defensively around this: if the
success-banner text never appears within the timeout, it is treated as a
zero-result search rather than crashing - but it is worth confirming this
against a real zero-result search before a full 60k-row run, and adjusting
NO_RESULT_HINTS below if the real markup differs.
"""

from selenium.webdriver.common.by import By

# --------------------------------------------------------------------------- #
# Search box + Search Documents / Start again buttons
# --------------------------------------------------------------------------- #

# <input name="documentNumbers" placeholder="Add document numbers separated by...">
SEARCH_INPUT = (By.NAME, "documentNumbers")

# <button><span>Search Documents</span></button>
SEARCH_BUTTON = (
    By.XPATH,
    "//button[.//span[normalize-space(text())='Search Documents']]",
)

# <button><span>Start again</span></button> - clears the form for a fresh search
START_AGAIN_BUTTON = (
    By.XPATH,
    "//button[.//span[normalize-space(text())='Start again']]",
)

# --------------------------------------------------------------------------- #
# Search result banner
# --------------------------------------------------------------------------- #
# Observed markup (success state), simplified:
#
#   <div class="NNBu3igWLVHuX8pbGfNe ...">
#     <div class="Stack-module__stack ... undefined">        <-- the "row"
#       <svg .../>                                            (green check icon)
#       <div class="Title-module__title ...">5 E-invoices found matching your search</div>
#       <span>25200087</span>
#       <span>251000178051</span>
#       ...
#     </div>
#   </div>
#
# The title text and the invoice-number spans are SIBLINGS under the same
# row div - that sibling relationship (not any hashed class) is what
# ArchivePage uses to pull out the returned invoice numbers, which is what
# keeps that part of the code resilient to a CSS module hash change.

# The leaf div whose own text is "... E-invoices found matching your search".
# `not(.//div)` excludes ancestor rows/wrappers that also "contain" this text
# by virtue of nesting the title div inside them - it isolates the actual
# leaf element.
RESULT_TITLE = (
    By.XPATH,
    "//div[contains(normalize-space(.), 'E-invoices found matching your search') "
    "and not(.//div)]",
)

# VERIFY_ON_NEXT_DEPLOY: best-effort catch-all for a possible "nothing found"
# message, in case ClearTax renders something other than "0 E-invoices found
# matching your search" for a zero-result search. Not required for normal
# operation (see docstring above) but useful for a human doing a spot-check.
NO_RESULT_HINTS = (
    By.XPATH,
    "//*[contains(translate(normalize-space(.), "
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'no documents found') "
    "or contains(translate(normalize-space(.), "
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '0 e-invoices found')]",
)

# --------------------------------------------------------------------------- #
# Document type radio buttons (XML / PDF) - PDF must always be forced
# --------------------------------------------------------------------------- #
# <label><input type="radio" value="XML" checked></label>
# <label><input type="radio" value="PDF"></label>
PDF_RADIO_INPUT = (By.XPATH, "//input[@type='radio' and @value='PDF']")

# --------------------------------------------------------------------------- #
# Print template dropdown (custom MUI combobox, not a native <select>)
# --------------------------------------------------------------------------- #
# Scoped to the table whose header row contains the text "Print template",
# so this can never collide with any other dropdown elsewhere on the page.
PRINT_TEMPLATE_TABLE = (By.XPATH, "//table[.//td[contains(., 'Print template')]]")

# The clickable "handle" button that opens the dropdown list.
PRINT_TEMPLATE_HANDLE = (
    By.XPATH,
    "//table[.//td[contains(., 'Print template')]]//button[@role='button']",
)

# The free-text filter box that appears once the dropdown is open.
PRINT_TEMPLATE_SEARCH_INPUT = (By.NAME, "state-search")

# An option inside the open list. `{value}` is substituted at runtime with
# the exact template name from the Excel sheet. Exact-text equality (rather
# than `contains`) matters here because several templates share a common
# prefix, e.g. TAX_SAMARA / TAX_SAMARA_ARAMCO / TAX_SAMARA_COBRA / TAX_SAMARA_JHAH.
PRINT_TEMPLATE_OPTION_TEMPLATE = (
    By.XPATH,
    "//div[@id='dropdown-wrapper']"
    "//span[contains(@class,'DropdownMenu-module__primary-label-text-styles')]"
    "[normalize-space(text())='{value}']",
)

# --------------------------------------------------------------------------- #
# Download button
# --------------------------------------------------------------------------- #
DOWNLOAD_BUTTON = (
    By.XPATH,
    "//button[.//span[normalize-space(text())='Download']]",
)

# --------------------------------------------------------------------------- #
# "Search invoices" tab
# --------------------------------------------------------------------------- #
# Loading the archive URL, or refreshing the page, lands on the "Generate
# reports" tab by default - which has none of the elements this automation
# needs (no document-number search box, no Search Documents button, etc.).
# This locator lets ArchivePage click back onto the "Search invoices" tab
# every time the page loads or reloads, rather than assuming it's already
# selected.
SEARCH_INVOICES_TAB = (
    By.XPATH,
    "//div[contains(@class,'Tabs-module__tabs') and normalize-space(text())='Search invoices']",
)
