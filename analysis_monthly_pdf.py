"""
analysis_monthly_pdf.py

ReportLab Platypus layout for AutoEDA's "Monthly Detailed Report"
(Report 2) — one outlet, one month, branch-level detail.

Reuses the page geometry, paragraph styles, and small helpers from
analysis_pdf.py (Report 1) rather than redefining them, so both reports
stay visually consistent (same A4-landscape geometry, same fonts). Only
the section layout itself is separate, since Report 2's structure (a KPI
block, branch-scoped wording) differs enough from Report 1 that sharing
those functions would mean threading report-specific text through
Report 1's code — not worth the coupling for what is fundamentally a
different report.

Pure ReportLab (no HTML/CSS, no system dependencies) — safe to bundle
with PyInstaller, same as analysis_pdf.py.
"""

import io

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
)

from analysis_pdf import (
    PAGE_SIZE,
    MARGIN,
    CONTENT_WIDTH,
    CONTENT_HEIGHT,
    TITLE_STYLE,
    SUBTITLE_STYLE,
    SECTION_STYLE,
    OUTLET_HEADING_STYLE,
    _image_flowable,
    _heading_block_height,
)


def _cover_page(outlet: str, month_label: str, generated_at) -> list:
    elements = [
        Spacer(1, 55 * mm),
        Paragraph("Monthly Detailed Report", TITLE_STYLE),
        Paragraph(f"Outlet: {outlet}", SUBTITLE_STYLE),
        Paragraph(f"Month: {month_label}", SUBTITLE_STYLE),
        Paragraph(f"Generated: {generated_at.strftime('%d %b %Y, %I:%M %p')}", SUBTITLE_STYLE),
        PageBreak(),
    ]
    return elements


def _kpi_table(kpis: dict) -> Table:
    """
    A simple 2-column label/value KPI block. Table (not a chart) since
    these are exact figures the manager will want to read precisely, not
    compare visually.
    """
    top_branch_text = "—"
    if kpis["top_branch"]:
        top_branch_text = f"{kpis['top_branch']}  (RM {kpis['top_branch_sales']:,.2f})"

    rows = [
        ["Total Sales", f"RM {kpis['total_sales']:,.2f}"],
        ["Total Invoices", f"{kpis['invoice_count']:,}"],
        ["Active Branches", f"{kpis['branch_count']:,}"],
        ["Average Transaction Value", f"RM {kpis['avg_transaction_value']:,.2f}"],
        ["Top Branch", top_branch_text],
    ]

    table = Table(rows, colWidths=[55 * mm, 90 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#2E5C8A")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#DDDDDD")),
            ]
        )
    )
    return table


def _section1_overview(outlet: str, month_label: str, kpis: dict, branch_overview_imgs: list) -> list:
    elements = []
    heading = Paragraph(f"1. Overview — {outlet} ({month_label})", SECTION_STYLE)
    kpi_table = _kpi_table(kpis)

    if not branch_overview_imgs:
        # No sales data at all for this outlet/month (shouldn't normally
        # happen since generate_monthly_detail_report raises earlier, but
        # kept as a safe fallback).
        elements.append(KeepTogether([heading, kpi_table]))
        elements.append(PageBreak())
        return elements

    for idx, img in enumerate(branch_overview_imgs):
        block = []
        headings = []
        if idx == 0:
            block.append(heading)
            headings.append(heading)
            block.append(Spacer(1, 6))
            block.append(kpi_table)
            block.append(Spacer(1, 10))
        reserved = _heading_block_height(headings, CONTENT_WIDTH) + 4
        if idx == 0:
            # KPI table also eats vertical space above the chart on the
            # first page — reserve room for it too.
            reserved += kpi_table.wrap(CONTENT_WIDTH, 10_000)[1] + 16

        block.append(_image_flowable(img, max_width=CONTENT_WIDTH, max_height=CONTENT_HEIGHT - reserved))
        elements.append(KeepTogether(block))
        elements.append(PageBreak())

    return elements


def _section2_branch_products(branch_totals, branch_chart_imgs: dict) -> list:
    """
    One branch per page, same pattern as Report 1's per-outlet product
    section — branches ordered by descending sales (same order as the
    branch comparison chart), each branch's product chart(s) paginated
    at 25 products/page upstream (analysis_monthly.py).
    """
    ordered_branches = list(branch_totals["Name"])

    elements = []
    first = True
    for branch in ordered_branches:
        for img in branch_chart_imgs.get(branch, []):
            block = []
            headings = []
            if first:
                section_heading = Paragraph("2. Product Sales per Branch", SECTION_STYLE)
                block.append(section_heading)
                headings.append(section_heading)
                first = False
            branch_heading = Paragraph(branch, OUTLET_HEADING_STYLE)
            block.append(branch_heading)
            headings.append(branch_heading)

            reserved = _heading_block_height(headings, CONTENT_WIDTH) + 4
            block.append(_image_flowable(img, max_width=CONTENT_WIDTH, max_height=CONTENT_HEIGHT - reserved))

            elements.append(KeepTogether(block))
            elements.append(PageBreak())

    return elements


def build_monthly_detail_pdf(
    output_path: str,
    outlet: str,
    month_label: str,
    generated_at,
    kpis: dict,
    branch_totals,
    branch_overview_imgs: list,
    branch_chart_imgs: dict,
) -> str:
    """
    Assemble the cover page + both sections into a single landscape A4
    PDF and save to output_path.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=PAGE_SIZE,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        title=f"Monthly Detailed Report - {outlet} - {month_label}",
    )

    story = []
    story += _cover_page(outlet, month_label, generated_at)
    story += _section1_overview(outlet, month_label, kpis, branch_overview_imgs)
    story += _section2_branch_products(branch_totals, branch_chart_imgs)

    # Last element is always a trailing PageBreak from the section
    # builders — ReportLab tolerates it, but drop it for a clean end.
    if story and isinstance(story[-1], PageBreak):
        story.pop()

    doc.build(story)
    return output_path
