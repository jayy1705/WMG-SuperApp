"""
analysis_monthly_pdf.py

ReportLab Platypus layout for AutoEDA's "Monthly Detailed Report"
(Report 2) — one outlet, one month, branch-level detail.

Reuses the page geometry, paragraph styles, and layout helpers from
analysis_pdf.py (Report 1) rather than redefining them, so both reports
stay visually consistent (same A4-landscape geometry, same fonts, same
chart-sizing arithmetic). Only what's genuinely Report-2 specific lives
here: the cover page, the KPI block, and the branch-scoped wording.

Pure ReportLab (no HTML/CSS, no system dependencies) — safe to bundle
with PyInstaller, same as analysis_pdf.py.
"""

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
)

from analysis_pdf import (
    PAGE_SIZE,
    MARGIN,
    CONTENT_WIDTH,
    TITLE_STYLE,
    SUBTITLE_STYLE,
    SECTION_STYLE,
    _chart_page,
    build_product_pages_section,
)


def _cover_page(outlet: str, month_label: str, generated_at) -> list:
    return [
        Spacer(1, 55 * mm),
        Paragraph("Monthly Detailed Report", TITLE_STYLE),
        Paragraph(f"Outlet: {outlet}", SUBTITLE_STYLE),
        Paragraph(f"Month: {month_label}", SUBTITLE_STYLE),
        Paragraph(f"Generated: {generated_at.strftime('%d %b %Y, %I:%M %p')}", SUBTITLE_STYLE),
        PageBreak(),
    ]


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
    """
    KPI block + branch comparison chart(s). The KPI table only appears on
    the first page; later pages (30+ branches) are chart-only.
    """
    elements = []
    for idx, img in enumerate(branch_overview_imgs):
        headings = []
        extra = []
        extra_height = 0

        if idx == 0:
            headings.append(Paragraph(f"1. Overview — {outlet} ({month_label})", SECTION_STYLE))
            kpi_table = _kpi_table(kpis)
            # The KPI table eats vertical space above the chart on the
            # first page — reserve room for it too.
            extra = [Spacer(1, 6), kpi_table, Spacer(1, 10)]
            extra_height = kpi_table.wrap(CONTENT_WIDTH, 10_000)[1] + 16

        elements.append(_chart_page(headings, img, extra=extra, extra_height=extra_height))
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
    story += build_product_pages_section(
        list(branch_totals["Name"]), branch_chart_imgs, "2. Product Sales per Branch"
    )

    # Last element is always a trailing PageBreak from the section
    # builders — ReportLab tolerates it, but drop it for a clean end.
    if story and isinstance(story[-1], PageBreak):
        story.pop()

    doc.build(story)
    return output_path
