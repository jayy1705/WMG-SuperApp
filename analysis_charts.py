"""
analysis_charts.py

matplotlib/seaborn chart builders for AutoEDA's Overall Sales Report.
Each function returns an io.BytesIO PNG buffer ready to hand to
analysis_pdf.py's ReportLab Image flowable — nothing is saved to disk.

Charts are sized to match the printable area of a landscape A4 page (see
_dynamic_figsize) so they fill the page instead of floating in a small
box surrounded by blank space. Categorical bar charts (barh) space their
bars evenly across whatever figure height they're given, so a fixed,
page-filling figsize makes both a 5-row and a 25-row chart look
deliberately sized rather than sparse or cramped.

Uses the non-interactive 'Agg' backend since this runs inside a Tkinter
app / packaged .exe with no matplotlib GUI window needed.
"""

import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid")

BAR_COLOR = "#2E5C8A"
ACCENT_COLOR = "#5DA9E9"
OTHERS_COLOR = "#B0B0B0"

# Matches the printable area of a landscape A4 page (content width/height
# in analysis_pdf.py), so charts fill the page by default instead of
# leaving blank space around a small, fixed-size figure.
PAGE_FIGSIZE = (13.5, 8.9)
MIN_ROW_HEIGHT = 0.34  # inches per bar, used once row count grows large


def _dynamic_figsize(n_rows: int, base_size=PAGE_FIGSIZE, min_row_height=MIN_ROW_HEIGHT):
    """
    Fill the page by default; only grow taller than the page when there
    are enough rows that MIN_ROW_HEIGHT per row would otherwise cramp them.
    """
    base_w, base_h = base_size
    height = max(base_h, n_rows * min_row_height)
    return (base_w, height)


def _fig_to_buffer(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _currency_formatter(x, pos):
    if x >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if x >= 1_000:
        return f"{x / 1_000:.0f}K"
    return f"{x:.0f}"


# ---------------------------------------------------------------------
# Chart 1: yearly overview — total sales per outlet, sorted descending
# ---------------------------------------------------------------------
def build_outlet_overview_chart(
    outlet_totals: pd.DataFrame,
    period_label: str = None,
    page_num: int = 1,
    total_pages: int = 1,
    name_col: str = "group",
    title: str = "Overall Sales by Outlet",
) -> io.BytesIO:
    """
    outlet_totals: columns [name_col, 'TotalSales'], already sorted desc,
    pre-paginated to <=30 rows by analysis.paginate_rows() so bars stay a
    readable thickness regardless of total row count.
    name_col: which column holds the bar labels — 'group' for outlets
    (Report 1, the default) or 'Name' for branches (Report 2).
    title: base chart title — defaults to the Report 1 wording; Report 2
    passes something like "Branch Sales Comparison" instead.
    page_num / total_pages: shown in the chart title when there was more
    than one page (e.g. "Page 2 of 2").
    """
    n = len(outlet_totals)
    figsize = _dynamic_figsize(n)
    fig, ax = plt.subplots(figsize=figsize)

    ax.barh(outlet_totals[name_col], outlet_totals["TotalSales"], color=BAR_COLOR)
    ax.invert_yaxis()  # highest sales at top
    ax.set_xlabel("Total Sales (RM)", fontsize=13)
    full_title = title
    if period_label:
        full_title += f"   |   Period: {period_label}"
    if total_pages > 1:
        full_title += f"   (Page {page_num} of {total_pages})"
    ax.set_title(full_title, fontsize=17, fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_currency_formatter))
    ax.tick_params(axis="y", labelsize=11)
    ax.tick_params(axis="x", labelsize=11)

    max_val = outlet_totals["TotalSales"].max()
    for i, value in enumerate(outlet_totals["TotalSales"]):
        ax.text(value + max_val * 0.005, i, f"{value:,.0f}", va="center", fontsize=10)

    fig.tight_layout()
    return _fig_to_buffer(fig)


# ---------------------------------------------------------------------
# Chart 2: product sales within a single outlet (one page per <=25 chunk)
# ---------------------------------------------------------------------
def build_outlet_product_chart(
    outlet_name: str,
    product_data: pd.DataFrame,
    total_sales: float,
    page_num: int = 1,
    total_pages: int = 1,
) -> io.BytesIO:
    """
    product_data: columns ['Description', 'Sales'] for ONE outlet, already
    paginated to <=25 rows by analysis.paginate_products().
    page_num / total_pages: shown in the chart title when an outlet needed
    more than one page (e.g. "Page 2 of 3").
    """
    n = len(product_data)
    figsize = _dynamic_figsize(n)
    fig, ax = plt.subplots(figsize=figsize)

    colors = [OTHERS_COLOR if desc == "Others" else ACCENT_COLOR for desc in product_data["Description"]]
    ax.barh(product_data["Description"], product_data["Sales"], color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("Sales (RM)", fontsize=13)

    title = f"{outlet_name} — Total Sales: RM {total_sales:,.2f}"
    if total_pages > 1:
        title += f"   (Page {page_num} of {total_pages})"
    ax.set_title(title, fontsize=15, fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_currency_formatter))
    ax.tick_params(axis="y", labelsize=11)
    ax.tick_params(axis="x", labelsize=11)

    max_val = product_data["Sales"].max()
    for i, value in enumerate(product_data["Sales"]):
        ax.text(value + max_val * 0.005, i, f"{value:,.0f}", va="center", fontsize=10)

    fig.tight_layout()
    return _fig_to_buffer(fig)


# ---------------------------------------------------------------------
# Chart 3: company-wide product % contribution (top N + Others), plus a
# drill-down donut breaking down what's inside "Others"
# ---------------------------------------------------------------------
def _build_donut(data: pd.DataFrame, title: str, legend_ncol: int = 2) -> io.BytesIO:
    """
    Shared donut-builder for both the main contribution chart and the
    "Others" breakdown chart. Uses an explicitly-positioned axes (instead
    of relying on tight_layout, which tends to shrink the pie to make
    room for an external legend) so the donut renders large regardless of
    how many legend entries there are.

    data: columns ['Description', 'Percent'] (+ 'Sales', unused here),
    already sorted descending.
    """
    n = len(data)
    fig = plt.figure(figsize=(15, 9.5))
    # Donut gets a big square-ish block on the left; legend lives in the
    # remaining space on the right. Fractions are figure-relative.
    ax = fig.add_axes([0.02, 0.05, 0.52, 0.88])

    palette = sns.color_palette("husl", n_colors=n)
    colors = [OTHERS_COLOR if desc == "Others" else palette[i] for i, desc in enumerate(data["Description"])]

    wedges, _ = ax.pie(
        data["Percent"],
        colors=colors,
        startangle=90,
        counterclock=False,
        radius=1.3,
        wedgeprops={"edgecolor": "white", "linewidth": 1, "width": 0.4},  # width<1 creates the donut ring
    )
    ax.set_title(title, fontsize=19, fontweight="bold", pad=20)
    ax.axis("equal")

    legend_labels = [f"{desc}  —  {pct:.1f}%" for desc, pct in zip(data["Description"], data["Percent"])]
    ax.legend(
        wedges,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.15, 0.5),
        fontsize=9,
        frameon=False,
        ncol=legend_ncol,
        columnspacing=1.3,
        labelspacing=0.7,
    )

    return _fig_to_buffer(fig)


def build_product_contribution_chart(product_contribution: pd.DataFrame) -> io.BytesIO:
    """
    product_contribution: columns ['Description', 'Sales', 'Percent']
    (output of analysis.product_contribution_overall()[0]), top N products
    + a single 'Others' row, sorted descending. Percent is share of total
    company-wide sales.
    """
    return _build_donut(product_contribution, "Product Contribution to Total Sales")


def build_others_breakdown_chart(
    others_breakdown: pd.DataFrame, others_total_sales: float, others_pct_of_grand_total: float
) -> io.BytesIO:
    """
    Drill-down donut showing what makes up the 'Others' slice from the
    main contribution chart. others_breakdown: columns
    ['Description', 'Sales', 'Percent'] (output of
    analysis.product_contribution_overall()[1]) — Percent here is each
    product's share of the OTHERS SUBTOTAL, so this chart's slices sum to
    100% on their own.
    """
    title = (
        f"\"Others\" Breakdown — RM {others_total_sales:,.2f}  "
        f"({others_pct_of_grand_total:.1f}% of Total Company-wide Sales)"
    )
    return _build_donut(others_breakdown, title, legend_ncol=3 if len(others_breakdown) > 30 else 2)
