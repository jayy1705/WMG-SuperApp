"""
analysis_pdf.py

ReportLab Platypus layout for AutoEDA's "Overall Sales Report" (Report 1).
Takes the pre-computed aggregation tables (analysis.py) and pre-rendered
chart PNGs (analysis_charts.py) and assembles them into a single A4 PDF.

Pure ReportLab (no HTML/CSS, no system dependencies) — safe to bundle
with PyInstaller.
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
    Table,
    TableStyle,
    KeepTogether,
)

PAGE_SIZE = landscape(A4)
MARGIN = 18 * mm
# SimpleDocTemplate's default Frame adds its own internal padding (~6pt per
# side) on top of the page margins — subtract a safety buffer so scaled
# images never exceed the actual usable frame area.
FRAME_PADDING_BUFFER = 16
CONTENT_WIDTH = PAGE_SIZE[0] - 2 * MARGIN - FRAME_PADDING_BUFFER
CONTENT_HEIGHT = PAGE_SIZE[1] - 2 * MARGIN - FRAME_PADDING_BUFFER

styles = getSampleStyleSheet()
TITLE_STYLE = ParagraphStyle(
    "ReportTitle", parent=styles["Title"], fontSize=22, spaceAfter=6,
)
SUBTITLE_STYLE = ParagraphStyle(
    "ReportSubtitle", parent=styles["Normal"], fontSize=12, textColor=colors.grey, spaceAfter=4,
)
SECTION_STYLE = ParagraphStyle(
    "SectionHeading", parent=styles["Heading1"], fontSize=15, spaceBefore=10, spaceAfter=8,
)
OUTLET_HEADING_STYLE = ParagraphStyle(
    "OutletHeading", parent=styles["Heading3"], fontSize=10, spaceBefore=2, spaceAfter=2,
)
BODY_STYLE = styles["Normal"]


def _image_flowable(png_buffer: io.BytesIO, max_width: float, max_height: float = None) -> Image:
    """
    Build a ReportLab Image flowable from a PNG buffer, scaled to fit
    max_width while preserving aspect ratio (and capped by max_height
    if given, shrinking further if needed).
    """
    png_buffer.seek(0)
    reader = ImageReader(png_buffer)
    iw, ih = reader.getSize()
    aspect = ih / iw

    width = max_width
    height = width * aspect

    if max_height is not None and height > max_height:
        height = max_height
        width = height / aspect

    png_buffer.seek(0)
    return Image(png_buffer, width=width, height=height)


def _heading_block_height(paragraphs: list, width: float) -> float:
    """
    Precisely measure the vertical space a list of Paragraph flowables
    will actually occupy (text height + each style's spaceBefore/After),
    so image height reservations aren't based on rough guesses that leave
    unclaimed blank space at the bottom of the page.
    """
    total = 0.0
    for p in paragraphs:
        w, h = p.wrap(width, 10_000)
        total += h + p.style.spaceBefore + p.style.spaceAfter
    return total


def _cover_page(period_label: str, generated_at, grand_total: float) -> list:
    elements = [
        Spacer(1, 60 * mm),
        Paragraph("Overall Sales Report", TITLE_STYLE),
        Paragraph(f"Period covered: {period_label}", SUBTITLE_STYLE),
        Paragraph(f"Generated: {generated_at.strftime('%d %b %Y, %I:%M %p')}", SUBTITLE_STYLE),
        Spacer(1, 12 * mm),
        Paragraph(f"Total Company-wide Sales: RM {grand_total:,.2f}", SECTION_STYLE),
        PageBreak(),
    ]
    return elements


def _section1_overview(chart1_imgs: list, period_label: str) -> list:
    elements = []
    for idx, img in enumerate(chart1_imgs):
        heading_text = f"1. Yearly Overview — Sales by Outlet ({period_label})"
        if len(chart1_imgs) > 1:
            heading_text += f" — Page {idx + 1} of {len(chart1_imgs)}"
        heading = Paragraph(heading_text, SECTION_STYLE)
        reserved = _heading_block_height([heading], CONTENT_WIDTH) + 4  # small safety buffer
        elements.append(
            KeepTogether(
                [
                    heading,
                    _image_flowable(img, max_width=CONTENT_WIDTH, max_height=CONTENT_HEIGHT - reserved),
                ]
            )
        )
        elements.append(PageBreak())
    return elements


def _section2_outlet_products(
    outlet_totals,
    outlet_chart_imgs: dict,
) -> list:
    """
    One outlet per page. If an outlet's chart was paginated (more than 25
    products => multiple chart images), each page image gets its own page
    with a "(Page X of Y)" marker already baked into the chart title.
    """
    ordered_outlets = list(outlet_totals["group"])

    elements = []
    first = True
    for outlet in ordered_outlets:
        for img in outlet_chart_imgs[outlet]:
            block = []
            headings = []
            if first:
                section_heading = Paragraph("2. Product Sales per Outlet", SECTION_STYLE)
                block.append(section_heading)
                headings.append(section_heading)
                first = False
            outlet_heading = Paragraph(outlet, OUTLET_HEADING_STYLE)
            block.append(outlet_heading)
            headings.append(outlet_heading)

            reserved = _heading_block_height(headings, CONTENT_WIDTH) + 4  # small safety buffer
            block.append(_image_flowable(img, max_width=CONTENT_WIDTH, max_height=CONTENT_HEIGHT - reserved))

            elements.append(KeepTogether(block))
            elements.append(PageBreak())

    return elements


def _section3_contribution(chart3_img: io.BytesIO, chart3b_img: io.BytesIO = None) -> list:
    heading = Paragraph("3. Product Contribution to Total Sales", SECTION_STYLE)
    reserved = _heading_block_height([heading], CONTENT_WIDTH) + 4  # small safety buffer
    elements = [
        KeepTogether(
            [
                heading,
                _image_flowable(chart3_img, max_width=CONTENT_WIDTH, max_height=CONTENT_HEIGHT - reserved),
            ]
        ),
    ]

    if chart3b_img is not None:
        elements.append(PageBreak())
        heading_b = Paragraph("3b. \u201cOthers\u201d — Detailed Breakdown", SECTION_STYLE)
        reserved_b = _heading_block_height([heading_b], CONTENT_WIDTH) + 4
        elements.append(
            KeepTogether(
                [
                    heading_b,
                    _image_flowable(chart3b_img, max_width=CONTENT_WIDTH, max_height=CONTENT_HEIGHT - reserved_b),
                ]
            )
        )

    return elements


def build_overall_sales_pdf(
    output_path: str,
    period_label: str,
    generated_at,
    outlet_totals,
    outlet_chart_imgs: dict,
    chart1_imgs: list,
    chart3_img: io.BytesIO,
    product_contribution,
    chart3b_img: io.BytesIO = None,
) -> str:
    """
    Assemble all sections into a single A4 PDF and save to output_path.
    outlet_chart_imgs: {"OUTLET NAME": [img_page1, img_page2, ...], ...}
    — a list per outlet since an outlet with >25 products spans multiple
    chart pages (see analysis.paginate_products).
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=PAGE_SIZE,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        title="Overall Sales Report",
    )

    grand_total = outlet_totals["TotalSales"].sum()

    story = []
    story += _cover_page(period_label, generated_at, grand_total)
    story += _section1_overview(chart1_imgs, period_label)
    story += _section2_outlet_products(outlet_totals, outlet_chart_imgs)
    story += _section3_contribution(chart3_img, chart3b_img)

    doc.build(story)
    return output_path