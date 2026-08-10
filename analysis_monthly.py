"""
analysis_monthly.py

Pure logic for AutoEDA's "Monthly Detailed Report" (Report 2): scoped to
ONE outlet and ONE month, chosen by the user in gui/step3_analyze.py via
gui/monthly_report_dialog.py. Shows that outlet's branch-level detail —
Report 1 never goes below the 'group' (outlet) level, this report is
where branch ('Name') level detail lives.

Reuses analysis.py's generic building blocks (sales_by_outlet_product
with group_col='Name', paginate_rows) and analysis_charts.py's generic
chart builders (build_outlet_overview_chart with name_col='Name',
build_outlet_product_chart) rather than duplicating that logic — only the
KPI computation and PDF layout (analysis_monthly_pdf.py) are Report-2
specific.

No GUI code here — import this from gui/step3_analyze.py the same way
analysis.py is imported for Report 1.
"""

from datetime import datetime

import pandas as pd

from analysis import prepare_dataframe, sales_by_outlet_product, paginate_rows


# ---------------------------------------------------------------------
# Dialog support — lists of outlets/months for the GUI selector
# ---------------------------------------------------------------------
def get_available_outlets(df: pd.DataFrame) -> list:
    """
    Sorted, de-duplicated list of outlet ('group') names for the GUI
    dropdown. Does not require DocDate parsing, so this can be called
    directly on the raw cleaned_df before prepare_dataframe().
    """
    if "group" not in df.columns:
        return []
    return sorted(df["group"].dropna().unique().tolist())


def get_available_months(df: pd.DataFrame) -> list:
    """
    Sorted list of (period, label) tuples for every month present in the
    data, e.g. (Period('2026-07'), 'Jul 2026'), for the GUI dropdown.
    period is what filter_to_outlet_month() expects; label is what the
    dropdown should display.
    """
    prepared = prepare_dataframe(df)
    months = sorted(prepared["Month"].unique())
    return [(m, m.strftime("%b %Y")) for m in months]


# ---------------------------------------------------------------------
# Filtering + KPIs
# ---------------------------------------------------------------------
def filter_to_outlet_month(df: pd.DataFrame, outlet: str, month) -> pd.DataFrame:
    """
    df: the cleaned_df (will be run through prepare_dataframe internally).
    outlet: a value from get_available_outlets().
    month: a Period from get_available_months() (the first tuple element).
    Returns the subset of rows for that outlet in that month. Empty
    DataFrame if there's no data for that combination.
    """
    prepared = prepare_dataframe(df)
    return prepared[(prepared["group"] == outlet) & (prepared["Month"] == month)].reset_index(drop=True)


def compute_kpis(filtered_df: pd.DataFrame) -> dict:
    """
    Summary KPIs for one outlet in one month:
      total_sales             sum(LineAmount)
      invoice_count            count of distinct DocNo
      branch_count              count of distinct Name (branches active
                                this month)
      avg_transaction_value    total_sales / invoice_count (0 if no
                                invoices)
      top_branch / top_branch_sales   the single highest-selling branch
                                and its sales figure (None if no data)
    """
    if filtered_df.empty:
        return {
            "total_sales": 0.0,
            "invoice_count": 0,
            "branch_count": 0,
            "avg_transaction_value": 0.0,
            "top_branch": None,
            "top_branch_sales": 0.0,
        }

    total_sales = filtered_df["LineAmount"].sum()
    invoice_count = filtered_df["DocNo"].nunique() if "DocNo" in filtered_df.columns else 0
    branch_count = filtered_df["Name"].nunique()
    avg_transaction_value = (total_sales / invoice_count) if invoice_count else 0.0

    branch_totals = filtered_df.groupby("Name")["LineAmount"].sum().sort_values(ascending=False)
    top_branch = branch_totals.index[0] if len(branch_totals) else None
    top_branch_sales = branch_totals.iloc[0] if len(branch_totals) else 0.0

    return {
        "total_sales": total_sales,
        "invoice_count": invoice_count,
        "branch_count": branch_count,
        "avg_transaction_value": avg_transaction_value,
        "top_branch": top_branch,
        "top_branch_sales": top_branch_sales,
    }


def sales_by_branch(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """
    Total LineAmount per branch 'Name', sorted descending.
    Returns columns: ['Name', 'TotalSales'].
    """
    if filtered_df.empty:
        return pd.DataFrame(columns=["Name", "TotalSales"])
    return (
        filtered_df.groupby("Name", as_index=False)["LineAmount"]
        .sum()
        .rename(columns={"LineAmount": "TotalSales"})
        .sort_values("TotalSales", ascending=False)
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------
def generate_monthly_detail_report(df: pd.DataFrame, outlet: str, month, output_path: str) -> str:
    """
    Full Report 2 pipeline for ONE outlet + ONE month: filter, compute
    KPIs + branch aggregations, build charts, lay out + save the PDF.
    Returns output_path on success.

    Raises ValueError if there's no data for the given outlet+month
    combination (e.g. the outlet made no sales that month).
    """
    from analysis_charts import build_outlet_overview_chart, build_outlet_product_chart
    from analysis_monthly_pdf import build_monthly_detail_pdf

    filtered = filter_to_outlet_month(df, outlet, month)
    if filtered.empty:
        raise ValueError(f"No data found for outlet '{outlet}' in the selected month.")

    month_label = month.strftime("%b %Y")
    kpis = compute_kpis(filtered)

    branch_totals = sales_by_branch(filtered)
    branch_products = sales_by_outlet_product(filtered, top_n=None, group_col="Name")

    # Branch comparison chart: same 30-per-page cap as Report 1's outlet
    # overview, for the same reason (bar thickness stays readable).
    branch_totals_pages = paginate_rows(branch_totals, max_per_page=30)
    total_branch_overview_pages = len(branch_totals_pages)
    branch_overview_imgs = [
        build_outlet_overview_chart(
            page_df,
            period_label=month_label,
            page_num=idx + 1,
            total_pages=total_branch_overview_pages,
            name_col="Name",
            title=f"{outlet} — Branch Sales Comparison",
        )
        for idx, page_df in enumerate(branch_totals_pages)
    ]

    # Per-branch product charts: same one-branch-per-page, 25-products-
    # per-page pattern as Report 1's per-outlet product charts.
    branch_chart_imgs = {}
    for branch, data in branch_products.items():
        pages = paginate_rows(data["products"], max_per_page=25)
        total_pages = len(pages)
        branch_chart_imgs[branch] = [
            build_outlet_product_chart(
                branch, page_df, data["total_sales"], page_num=idx + 1, total_pages=total_pages
            )
            for idx, page_df in enumerate(pages)
        ]

    build_monthly_detail_pdf(
        output_path=output_path,
        outlet=outlet,
        month_label=month_label,
        generated_at=datetime.now(),
        kpis=kpis,
        branch_totals=branch_totals,
        branch_overview_imgs=branch_overview_imgs,
        branch_chart_imgs=branch_chart_imgs,
    )

    return output_path
