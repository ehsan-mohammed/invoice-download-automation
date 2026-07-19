# ClearTax Invoice Download Automation

A Selenium + pandas framework that goes row-by-row through the
`grouped_invoices_by_template_1807.xlsx` sheet (62,440 rows), searches each
row's group of invoice numbers together on the ClearTax e-invoicing
Archives page, and downloads whatever PDF(s) that search returns -
logging every individual invoice number that couldn't be found instead of
silently skipping it.

Built for a ~60,000-row sheet: resumable, retries transient UI hiccups,
periodically refreshes the page and checkpoints progress, and shuts down
cleanly on Ctrl+C.

## The input sheet

`input/grouped_invoices_by_template_1807.xlsx` has two columns:

| Grouped_Invoice_Numbers | Print_Template |
|---|---|
| 251000169511, 251000023518, 251000178051, 251000057569, 25200087 | TAX_SAMARA |

- `Grouped_Invoice_Numbers` - a comma-separated list of invoice numbers to
  search for **together** in one search. Most rows have 5 numbers, but the
  parser makes no assumption about group size (1, 3, and 4 all occur in
  the real sheet too).
- `Print_Template` - must exactly match one of the site's dropdown options
  (confirmed against the real data: `TAX_SAMARA_COBRA`, `SIMPLIFIED_SAMARA`,
  `TAX_SAMARA_ARAMCO`, `TAX_SAMARA`, `TAX_SAMARA_JHAH`).

If you swap in a different file, just make sure `config.EXCEL_FILE` points
at it (or drop the replacement into `input/` under the same filename).

## How it works, step by step

1. Join that row's invoice numbers with a comma and paste them into
   **Search by document number(s)**, click **Search Documents**.
2. Read the result banner ("N E-invoices found matching your search") -
   the count is never trusted on its own; the individual invoice numbers
   listed alongside it are always parsed and compared against what the
   row expected.
3. Every expected invoice number that the site did **not** return is
   logged to `output/failures.csv` individually - `ExcelRow,
   MissingInvoice, PrintTemplate` - never just the grouped string.
4. The row is only skipped entirely if **none** of its expected invoices
   were found. If even 1 of 5 was found, the automation still proceeds:
   the **PDF** radio is forced on, the **Print template** dropdown is set
   to that row's `Print_Template`, and **Download** is clicked.
5. The script watches the download folder directly (diffing its contents
   and waiting for Chrome's `.crdownload` marker to disappear) rather than
   guessing a fixed delay, then moves to the next row.


## One-time setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Launch a dedicated, automation-controlled Chrome window

This script **never automates login** - it attaches to a Chrome window you
sign in to yourself. Start Chrome with a remote-debugging port and a
separate profile folder (so it doesn't touch your everyday Chrome profile):

```bat
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
    --remote-debugging-port=9222 ^
    --user-data-dir="C:\ChromeAutomation"
```

In the window that opens, navigate to the ClearTax e-invoicing portal and
sign in normally. Leave it open.

### 3. Point config.py at your files

Open `config.py` and check/adjust:

- `EXCEL_FILE` - already set to `input/grouped_invoices_by_template_1807.xlsx`
- `DOWNLOAD_FOLDER` - already set to
  `C:\Users\LENOVO\OneDrive - Samara Trading & Contracting Co\Invoices`
- `COL_GROUPED_INVOICE_NUMBERS` / `COL_PRINT_TEMPLATE` - only if your
  sheet's headers ever differ from `Grouped_Invoice_Numbers` /
  `Print_Template`

Any of these can also be overridden with an environment variable of the
same name instead of editing the file (see the `_str` / `_int` / `_bool`
helpers at the top of `config.py`).

**Important - Chrome's own download prompts:** make sure Chrome is set to
download automatically without asking "keep/save as" every time, and that
its default download folder matches `DOWNLOAD_FOLDER` above (or configure
it to always save to that folder). This is a one-time Chrome setting, not
something this script controls.

### 4. Run it

```bash
python main.py
```

A progress bar (via `tqdm`) shows overall row progress; `logs/automation.log`
has the detailed per-row trail.

### 5. Resuming

If the script stops for any reason - Ctrl+C, a crash, the machine sleeping -
just run `python main.py` again. It reads `output/progress.json` and
continues immediately after the last row that fully completed.

## Output files

| File | Contents |
|---|---|
| `logs/automation.log` | One line per event: search, found/missing counts, download result |
| `output/failures.csv` | `ExcelRow, MissingInvoice, PrintTemplate` - one row per individual invoice number that could not be found/downloaded |
| `output/progress.json` | `{"last_completed_row": N}` - used for resuming |

## Configuration knobs (all in `config.py`)

| Setting | Default | Meaning |
|---|---|---|
| `CHECKPOINT_INTERVAL` | 25 | Rows between `progress.json` saves |
| `REFRESH_AFTER_ROWS` | 500 | Rows between full page refreshes (React apps can drift over many hours) |
| `WAIT_TIMEOUT` | 20s | Generic explicit-wait timeout |
| `SEARCH_RESULT_TIMEOUT` | 30s | How long to wait for the results banner |
| `DOWNLOAD_TIMEOUT` | 90s | How long to wait for a PDF to finish downloading |
| `RETRY_ATTEMPTS` | 3 | Retries on flaky-UI exceptions (stale element, click intercepted, timeout) |
| `CLOSE_BROWSER_ON_EXIT` | False | Whether to close the attached Chrome window when the script ends |

## Two things worth verifying before a full 60k-row run

These are flagged inline as `VERIFY_ON_NEXT_DEPLOY` comments in
`locators.py`, but worth calling out explicitly:

1. **The "zero results" banner was never captured.** The HTML snapshot this
   project's locators were built from only showed a successful "N found"
   search. `ArchivePage.get_search_result()` is written to treat a missing
   banner as zero results rather than crash, but it's worth manually
   running one search you know will return nothing and confirming the
   result still gets logged the way you'd expect.
2. **ClearTax's CSS module class names carry a build-hash suffix**
   (e.g. `_3-3-16`) that will change on their next frontend deploy. Every
   locator in `locators.py` is built primarily from stable attributes
   (`name=`, visible button text, parent/sibling DOM relationships) for
   exactly this reason, but if ClearTax ships a redesign mid-run, this is
   the one file to check first.

## Project layout

```
invoice_automation/
  main.py                  Entry point / row loop
  config.py                All tunables in one place
  locators.py               All Selenium locators, with rationale comments
  pages/
    archive_page.py         Page Object - the only place that "speaks Selenium"
  core/
    browser.py              Attaches to the already-open Chrome (no login)
    waits.py                 Explicit-wait helpers
    retry.py                 Retry decorator for flaky-UI exceptions
    logger.py                 automation.log setup
    progress.py               Resume support (progress.json)
    downloader.py             Folder-diff based download-completion detection
    comparator.py              Expected-vs-found invoice comparison (pure logic, browser-free)
    excel.py                   Reads the sheet, writes failures.csv
  logs/                       automation.log lands here
  output/                     progress.json + failures.csv land here
  input/                      grouped_invoices_by_template_1807.xlsx lives here
  requirements.txt
```
