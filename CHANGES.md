# SuperApp cleanup — what changed

No behaviour changes. Verified against the original code on a 3,000-row synthetic
dataset: identical aggregation output, identical PDF page counts, identical PDF
text, and byte-identical PDF file sizes for both reports.

## Removed (dead / unused code)

| File | Removed |
|---|---|
| `analysis.py` | `classify_outlet_size()` — marked DEPRECATED, called nowhere |
| `analysis.py` | `__main__` demo block reading `test_output/sample.csv` |
| `analysis_pdf.py` | `product_contribution` parameter of `build_overall_sales_pdf()` — accepted, never used |
| `analysis_pdf.py` | Unused imports `Table`, `TableStyle`; unused `BODY_STYLE` |
| `analysis_monthly_pdf.py` | Unused `import io` |
| `analysis_monthly_pdf.py` | The `if not branch_overview_imgs:` fallback — unreachable, since `generate_monthly_detail_report()` raises on empty data before this point |
| `InvoiceConverter.py` | `write_csv()` + its `csv` import — the app uses `df.to_csv()` |
| `InvoiceConverter.py` | Unpacking of columns 16–17 (never referenced); row padding trimmed from 18 to 16 |
| `mapping_editor.py` | `sorted_pairs` in `_selected_index()` — computed, never used |
| `gui/monthly_report_dialog.py` | "No outlet/month data available" label + disabled-button branch — Step 3 checks this before opening the dialog |
| `mapping_store.py` | 2 exact duplicate rows in `DEFAULT_MAPPING` (425 → 423 entries), reformatted to consistent indentation |

## Merged (duplicated logic now in one place)

- **`sales_by_branch()` deleted.** It was `sales_by_outlet()` with a different
  column name. `analysis.sales_by_outlet()` now takes `group_col`, and Report 2
  calls it with `group_col="Name"` — mirroring how it already shared
  `sales_by_outlet_product()`.
- **Top-N/"Others" bucketing** was written twice (`sales_by_outlet_product`,
  `product_contribution_overall`). Now one helper: `analysis._bucket_others()`.
- **The two `barh` chart builders** were ~25 near-identical lines each. Both now
  call `analysis_charts._build_barh()`; they only supply title, colours and label
  column. Page markers moved to `_paged_title()`.
- **"Product sales per outlet/branch" PDF section** existed twice
  (`analysis_pdf._section2_outlet_products`, `analysis_monthly_pdf._section2_branch_products`).
  Now one public `analysis_pdf.build_product_pages_section(order, chart_imgs, title)`,
  used by both reports. It also uses `.get(name, [])`, so a missing chart key no
  longer raises `KeyError` in Report 1.
- **The "heading + image scaled to remaining page height" arithmetic** was repeated
  in five places. Now `analysis_pdf._chart_page(headings, img, extra, extra_height)`;
  Report 2's KPI table passes through `extra`.
- **`_run_yearly()` / `_run_monthly()`** in `gui/step3_analyze.py` were the same
  try/except/`self.after` wrapper twice. Now one `_run_in_background(func, *args)`
  (both report functions return the output path). Empty-data guard folded into
  `_has_data()`.

## Tidied (comments / docstrings only)

- `InvoiceConverter.py` header said it was "extracted from InvoiceConverter.py"
  and named the module `invoice_converter.py`.
- `cleaning.py` section comments were numbered 2, 3, 4, 5, 6, 6b, 7 with no 1;
  renumbered 1–8. Stray trailing whitespace removed. References to `app.py`
  (which no longer exists) updated to `gui/step2_clean.py`.
- `main.py`: "Step 3: Analyze (placeholder until AutoEDA is ready)" — AutoEDA is ready.
- `mapping_editor.py`: "Open this from app.py".

## Unchanged

`gui/__init__.py`, `gui/step1_convert.py`, `gui/step2_clean.py` — nothing dead or
duplicated found in these.

## One data issue, left alone deliberately

`mapping_store.py` maps `'BAHAU ZEMART SDN BHD'` to the group
`'TABAHAU ZEMART SDN BHD'`, which looks like a typo for `'BAHAU ZEMART SDN BHD'`
(compare the neighbouring `MANTIN ZEMART` / `SENAWANG ZEMART` entries). That's a
data fix, not a code cleanup, so it's untouched — and note `DEFAULT_MAPPING` only
seeds `mapping.csv` on first run, so on an existing install you'd fix it through
**Manage Customer Names** instead.
