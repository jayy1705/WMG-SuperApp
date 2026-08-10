"""
analysis.py

Pure logic for AutoEDA's "Overall Sales Report" (Report 1): aggregation
functions plus the top-level orchestration function that ties aggregation,
chart generation (analysis_charts.py), and PDF layout (analysis_pdf.py)
together.

Expects the cleaned/grouped DataFrame produced by Step 2 (cleaning.py's
process()), which already has a 'group' column. No GUI code here — import
this from gui/step3_analyze.py the same way step2_clean.py imports
cleaning.py.
"""

from datetime import datetime

import pandas as pd

REQUIRED_COLUMNS = ["DocDate", "group", "Description", "LineAmount"]


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------
def validate_columns(df: pd.DataFrame) -> None:
    """
    Raise a clear ValueError if any column Report 1 depends on is missing,
    instead of letting a KeyError surface deep inside an aggregation.
    """
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Data is missing required column(s) for the Overall Sales Report: {missing}"
        )


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate required columns, parse DocDate to datetime, and derive a
    'Month' period column (e.g. 2026-07) used for period-range display.
    Returns a copy — does not mutate the original.
    """
    validate_columns(df)
    df = df.copy()
    df["DocDate"] = pd.to_datetime(df["DocDate"], errors="coerce")

    bad_dates = df["DocDate"].isna().sum()
    if bad_dates:
        print(f"WARNING: {bad_dates} row(s) had an unparseable DocDate and were dropped.")
        df = df.dropna(subset=["DocDate"])

    df["Month"] = df["DocDate"].dt.to_period("M")
    return df


def get_period_label(df: pd.DataFrame) -> str:
    """
    Human-readable date range covered by the data, e.g. 'Jan 2026 - Jul 2026'
    or just 'Jul 2026' if only one month is present.
    """
    months = sorted(df["Month"].unique())
    if not months:
        return "No data"
    start, end = months[0], months[-1]
    if start == end:
        return start.strftime("%b %Y")
    return f"{start.strftime('%b %Y')} - {end.strftime('%b %Y')}"


# ---------------------------------------------------------------------
# Chart 1: sales by outlet (group), sorted descending
# ---------------------------------------------------------------------
def sales_by_outlet(df: pd.DataFrame) -> pd.DataFrame:
    """
    Total LineAmount per outlet 'group', sorted descending.
    Returns columns: ['group', 'TotalSales'].
    """
    out = (
        df.groupby("group", as_index=False)["LineAmount"]
        .sum()
        .rename(columns={"LineAmount": "TotalSales"})
        .sort_values("TotalSales", ascending=False)
        .reset_index(drop=True)
    )
    return out


# ---------------------------------------------------------------------
# Chart 2: product sales per outlet (top N + Others), plus outlet size
# classification for PDF page layout
# ---------------------------------------------------------------------
def sales_by_outlet_product(df: pd.DataFrame, top_n: int = None, group_col: str = "group") -> dict:
    """
    For each value of group_col (default 'group' i.e. outlet; pass
    group_col='Name' for branch-level grouping, used by Report 2):
    product sales by LineAmount, sorted descending, plus that group's
    grand total.

    top_n: if given, only the top N products are kept individually and
    the rest are bucketed into an 'Others' row. If None (default), ALL
    products for that group are included with no cap.

    Returns a dict keyed by group_col value:
        {
            "NAME": {
                "total_sales": float,
                "products": pd.DataFrame with columns ['Description', 'Sales'],
                            sorted desc (all products, or top_n + 'Others'
                            if top_n was given),
            },
            ...
        }
    """
    result = {}
    grouped = df.groupby([group_col, "Description"], as_index=False)["LineAmount"].sum()

    for key, key_df in grouped.groupby(group_col):
        key_df = key_df.sort_values("LineAmount", ascending=False).reset_index(drop=True)
        total_sales = key_df["LineAmount"].sum()

        if top_n is not None and len(key_df) > top_n:
            top = key_df.iloc[:top_n].copy()
            others_sum = key_df.iloc[top_n:]["LineAmount"].sum()
            others_row = pd.DataFrame([{"Description": "Others", "LineAmount": others_sum}])
            products = pd.concat([top, others_row], ignore_index=True)
        else:
            products = key_df.copy()

        products = products.rename(columns={"LineAmount": "Sales"})[["Description", "Sales"]]

        result[key] = {
            "total_sales": total_sales,
            "products": products,
        }

    return result


def classify_outlet_size(outlet_totals: pd.DataFrame, big_quantile: float = 0.75) -> dict:
    """
    DEPRECATED: no longer used now that every outlet gets its own page(s)
    (see paginate_products below). Kept only in case a future layout wants
    it back.
    """
    if outlet_totals.empty:
        return {}
    cutoff = outlet_totals["TotalSales"].quantile(big_quantile)
    return {
        row["group"]: ("big" if row["TotalSales"] >= cutoff else "small")
        for _, row in outlet_totals.iterrows()
    }


def paginate_rows(data: pd.DataFrame, max_per_page: int = 25) -> list:
    """
    Split any DataFrame into chunks of at most max_per_page rows,
    preserving the existing sort order. Returns a list of DataFrames —
    one per PDF page needed. Used both for per-outlet product charts
    (chart 2) and the outlet overview chart (chart 1) once row counts
    get large enough that bars would otherwise get too thin to read.
    """
    if len(data) <= max_per_page:
        return [data.reset_index(drop=True)]
    return [
        data.iloc[i : i + max_per_page].reset_index(drop=True)
        for i in range(0, len(data), max_per_page)
    ]


# ---------------------------------------------------------------------
# Chart 3: company-wide product % contribution (top N + Others)
# ---------------------------------------------------------------------
def product_contribution_overall(df: pd.DataFrame, top_n: int = 30):
    """
    Company-wide product sales as a % of total sales.

    Returns a tuple (primary, others_breakdown):
      - primary: top N products individually + one 'Others' row bucketing
        the rest, sorted descending. Columns: ['Description', 'Sales', 'Percent']
        — Percent is share of TOTAL company-wide sales.
      - others_breakdown: every product NOT in the top N (i.e. everything
        that got folded into 'Others' above), sorted descending. Columns:
        ['Description', 'Sales', 'Percent'] — Percent here is share of the
        OTHERS SUBTOTAL (so this breakdown sums to 100% on its own), since
        it's meant to be charted as its own drill-down donut. Empty
        DataFrame if there were <= top_n products total (nothing to break
        down).
    """
    totals = (
        df.groupby("Description", as_index=False)["LineAmount"]
        .sum()
        .rename(columns={"LineAmount": "Sales"})
        .sort_values("Sales", ascending=False)
        .reset_index(drop=True)
    )
    grand_total = totals["Sales"].sum()

    if len(totals) > top_n:
        top = totals.iloc[:top_n].copy()
        others_breakdown = totals.iloc[top_n:].copy().reset_index(drop=True)
        others_sum = others_breakdown["Sales"].sum()
        others_breakdown["Percent"] = (
            (others_breakdown["Sales"] / others_sum * 100) if others_sum else 0.0
        )

        others_row = pd.DataFrame([{"Description": "Others", "Sales": others_sum}])
        primary = pd.concat([top, others_row], ignore_index=True)
    else:
        primary = totals.copy()
        others_breakdown = pd.DataFrame(columns=["Description", "Sales", "Percent"])

    primary["Percent"] = (primary["Sales"] / grand_total * 100) if grand_total else 0.0
    return primary, others_breakdown


# ---------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------
def generate_overall_sales_report(df: pd.DataFrame, output_path: str) -> str:
    """
    Full Report 1 pipeline: prepare data, run all aggregations, build
    charts (analysis_charts.py), and lay out + save the PDF
    (analysis_pdf.py). Returns output_path on success.
    """
    # Local imports so analysis.py stays importable/testable even before
    # analysis_charts.py / analysis_pdf.py exist or if matplotlib/reportlab
    # aren't needed (e.g. unit-testing aggregation logic alone).
    from analysis_charts import (
        build_outlet_overview_chart,
        build_outlet_product_chart,
        build_product_contribution_chart,
        build_others_breakdown_chart,
    )
    from analysis_pdf import build_overall_sales_pdf

    df = prepare_dataframe(df)
    period_label = get_period_label(df)

    outlet_totals = sales_by_outlet(df)
    outlet_products = sales_by_outlet_product(df, top_n=None)  # all products, no cap
    product_contribution, others_breakdown = product_contribution_overall(df, top_n=30)

    # Outlet overview: 30 outlets per page/chart, so bars stay a readable
    # thickness instead of getting squeezed as outlet count grows.
    outlet_totals_pages = paginate_rows(outlet_totals, max_per_page=30)
    total_outlet_overview_pages = len(outlet_totals_pages)
    chart1_imgs = [
        build_outlet_overview_chart(
            page_df, period_label=period_label, page_num=idx + 1, total_pages=total_outlet_overview_pages
        )
        for idx, page_df in enumerate(outlet_totals_pages)
    ]

    chart3_img = build_product_contribution_chart(product_contribution)

    chart3b_img = None
    if not others_breakdown.empty:
        others_total = others_breakdown["Sales"].sum()
        others_pct_of_grand_total = (
            product_contribution.loc[product_contribution["Description"] == "Others", "Percent"].iloc[0]
        )
        chart3b_img = build_others_breakdown_chart(others_breakdown, others_total, others_pct_of_grand_total)

    # One outlet per page; if an outlet has more than 25 products, split
    # it across multiple pages (25 products per chart/page).
    outlet_chart_imgs = {}
    for outlet, data in outlet_products.items():
        pages = paginate_rows(data["products"], max_per_page=25)
        total_pages = len(pages)
        outlet_chart_imgs[outlet] = [
            build_outlet_product_chart(
                outlet, page_df, data["total_sales"], page_num=idx + 1, total_pages=total_pages
            )
            for idx, page_df in enumerate(pages)
        ]

    build_overall_sales_pdf(
        output_path=output_path,
        period_label=period_label,
        generated_at=datetime.now(),
        outlet_totals=outlet_totals,
        outlet_chart_imgs=outlet_chart_imgs,
        chart1_imgs=chart1_imgs,
        chart3_img=chart3_img,
        chart3b_img=chart3b_img,
        product_contribution=product_contribution,
    )

    return output_path


if __name__ == "__main__":
    # Quick manual check when running `python analysis.py` directly
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "test_output/sample.csv"
    raw = pd.read_csv(path)
    prepared = prepare_dataframe(raw)

    print("Period:", get_period_label(prepared))
    print()
    print("Sales by outlet:")
    print(sales_by_outlet(prepared))
    print()
    primary, others = product_contribution_overall(prepared)
    print("Product contribution (top 30 + Others):")
    print(primary)
    print()
    print("Others breakdown:")
    print(others)
