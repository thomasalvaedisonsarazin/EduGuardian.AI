"""PDF renderer (reportlab platypus, A4, built-in Helvetica only).

Layout: running header (school, report title, exam, date), key-figure grid, key findings,
sections with zebra-striped tables that split across pages (header row repeats), a bar chart of
pass % and a footer with the EduGuardian notice and page numbers. Pass/fail is shown as text
*and* colour so the report reads correctly when printed in greyscale.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)
from reportlab.platypus import Table as RLTable

from app.reports.content import (
    NEGATIVE_STATUSES,
    POSITIVE_STATUSES,
    WARNING_STATUSES,
    BarChart,
    CellValue,
    Column,
    ReportContent,
    Table,
)

logger = logging.getLogger(__name__)

__all__ = ["render_pdf"]

BRAND = colors.HexColor("#4F46E5")
BRAND_DARK = colors.HexColor("#312E81")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
ZEBRA = colors.HexColor("#F1F5F9")
GRID = colors.HexColor("#CBD5E1")
PASS_BG = colors.HexColor("#DCFCE7")
PASS_FG = colors.HexColor("#166534")
FAIL_BG = colors.HexColor("#FEE2E2")
FAIL_FG = colors.HexColor("#991B1B")
WARN_BG = colors.HexColor("#FEF3C7")
WARN_FG = colors.HexColor("#92400E")
FIGURE_BG = colors.HexColor("#EEF2FF")

MARGIN = 15 * mm
LANDSCAPE_MIN_COLUMNS = 11
NARROW_TABLE_COLUMNS = 3


def plain_text(value: str) -> str:
    """Make text renderable with the standard Helvetica (cp1252) font (canvas strings)."""
    replacements = {"→": "->", "←": "<-", "≤": "<=", "≥": ">=", "₹": "Rs."}
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    return value.encode("cp1252", errors="replace").decode("cp1252")


def safe_text(value: str) -> str:
    """``plain_text`` + XML escaping for Paragraph markup."""
    return escape(plain_text(value))


def format_cell(value: CellValue, column: Column) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    if column.kind == "int":
        return str(value)
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    if column.kind == "percent":
        return f"{number:.2f}%"
    if column.kind == "decimal":
        return str(value) if isinstance(value, int) else f"{number:.2f}"
    if column.kind == "delta":
        if isinstance(value, int):
            return f"{value:+d}"
        return f"{number:+.2f}"
    if number == number.to_integral_value():
        return str(number.quantize(Decimal(1)))
    return f"{number:.2f}"


class _Styles:
    def __init__(self) -> None:
        base = getSampleStyleSheet()
        self.title = ParagraphStyle(
            "RTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20,
            leading=24, textColor=BRAND_DARK, alignment=0, spaceAfter=2,
        )  # fmt: skip
        self.subtitle = ParagraphStyle(
            "RSub", parent=base["Normal"], fontName="Helvetica", fontSize=10.5,
            textColor=MUTED, leading=14, spaceAfter=8,
        )  # fmt: skip
        self.h2 = ParagraphStyle(
            "RH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13.5,
            textColor=BRAND_DARK, spaceBefore=10, spaceAfter=6, leading=17,
        )  # fmt: skip
        self.h3 = ParagraphStyle(
            "RH3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10.5,
            textColor=INK, spaceBefore=6, spaceAfter=4, leading=13,
        )  # fmt: skip
        self.body = ParagraphStyle(
            "RBody", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, leading=13,
            textColor=INK, spaceAfter=4,
        )  # fmt: skip
        self.bullet = ParagraphStyle(
            "RBullet", parent=self.body, leftIndent=12, bulletIndent=2, spaceAfter=2,
        )  # fmt: skip
        self.note = ParagraphStyle(
            "RNote", parent=self.body, fontSize=8, leading=10, textColor=MUTED, spaceAfter=6,
        )  # fmt: skip
        self.cell = ParagraphStyle(
            "RCell", parent=self.body, fontSize=8, leading=9.6, spaceAfter=0,
        )  # fmt: skip
        self.cell_right = ParagraphStyle("RCellR", parent=self.cell, alignment=TA_RIGHT)
        self.head = ParagraphStyle(
            "RHead", parent=self.cell, fontName="Helvetica-Bold", textColor=colors.white,
        )  # fmt: skip
        self.head_right = ParagraphStyle("RHeadR", parent=self.head, alignment=TA_RIGHT)
        self.fig_value = ParagraphStyle(
            "RFigV", parent=self.body, fontName="Helvetica-Bold", fontSize=15, leading=18,
            textColor=BRAND_DARK, spaceAfter=0,
        )  # fmt: skip
        self.fig_label = ParagraphStyle(
            "RFigL", parent=self.body, fontSize=8, leading=10, textColor=MUTED, spaceAfter=0,
        )  # fmt: skip


def _figures_grid(content: ReportContent, styles: _Styles, width: float) -> Flowable | None:
    if not content.figures:
        return None
    per_row = 3
    cells: list[list[Any]] = []
    row: list[Any] = []
    for fig in content.figures:
        parts = [
            Paragraph(safe_text(fig.label.upper()), styles.fig_label),
            Paragraph(safe_text(fig.value), styles.fig_value),
        ]
        if fig.hint:
            parts.append(Paragraph(safe_text(fig.hint), styles.fig_label))
        row.append(parts)
        if len(row) == per_row:
            cells.append(row)
            row = []
    if row:
        cells.append(row + [""] * (per_row - len(row)))
    grid = RLTable(cells, colWidths=[width / per_row] * per_row)
    grid.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), FIGURE_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.white),
                ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return grid


def _status_colors(text: str) -> tuple[colors.Color, colors.Color] | None:
    if text in NEGATIVE_STATUSES:
        return FAIL_BG, FAIL_FG
    if text in POSITIVE_STATUSES:
        return PASS_BG, PASS_FG
    if text in WARNING_STATUSES:
        return WARN_BG, WARN_FG
    return None


def _table_flowables(table: Table, styles: _Styles, width: float) -> list[Flowable]:
    out: list[Flowable] = [Paragraph(safe_text(table.title), styles.h3)]
    if not table.rows:
        out.append(Paragraph(safe_text(table.empty_message), styles.body))
        return out
    numeric = {"int", "number", "decimal", "percent", "delta"}
    header = [
        Paragraph(safe_text(c.header), styles.head_right if c.kind in numeric else styles.head)
        for c in table.columns
    ]
    data: list[list[Any]] = [header]
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for r_idx, row in enumerate(table.rows, start=1):
        cells: list[Any] = []
        for c_idx, (value, column) in enumerate(zip(row, table.columns, strict=True)):
            text = format_cell(value, column)
            flagged = (r_idx - 1, c_idx) in table.flagged
            style = styles.cell_right if column.kind in numeric else styles.cell
            markup = safe_text(text)
            status = _status_colors(text) if column.kind == "status" else None
            if status is not None:
                bg, fg = status
                commands.append(("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), bg))
                markup = f'<font color="#{fg.hexval()[2:]}"><b>{markup}</b></font>'
            elif flagged:
                commands.append(("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), FAIL_BG))
                markup = f"<b>{markup}</b>"
            cells.append(Paragraph(markup, style))
        data.append(cells)
    if len(table.columns) <= NARROW_TABLE_COLUMNS:
        width *= 0.6
    total_weight = sum(c.weight for c in table.columns) or 1.0
    widths = [width * c.weight / total_weight for c in table.columns]
    rl_table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    rl_table.setStyle(TableStyle(commands))
    out.append(rl_table)
    if table.note:
        out.append(Spacer(1, 2))
        out.append(Paragraph(safe_text(table.note), styles.note))
    return out


def _chart(chart: BarChart, width: float) -> Drawing:
    height = 70 * mm
    drawing = Drawing(width, height)
    bc = VerticalBarChart()
    bc.x = 30
    bc.y = 38
    bc.width = width - 45
    bc.height = height - 60
    bc.data = [chart.values]
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 100
    bc.valueAxis.valueStep = 20
    bc.valueAxis.labels.fontName = "Helvetica"
    bc.valueAxis.labels.fontSize = 7
    bc.categoryAxis.categoryNames = [plain_text(label)[:22] for label in chart.labels]
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.boxAnchor = "ne"
    bc.categoryAxis.labels.angle = 25 if len(chart.labels) > 5 else 0
    bc.categoryAxis.labels.dy = -2
    bc.bars[0].fillColor = BRAND
    bc.bars[0].strokeColor = None
    bc.barLabelFormat = "%.1f%%"
    bc.barLabels.fontName = "Helvetica"
    bc.barLabels.fontSize = 7
    bc.barLabels.nudge = 6
    drawing.add(bc)
    drawing.add(
        String(
            0,
            height - 12,
            plain_text(chart.title),
            fontName="Helvetica-Bold",
            fontSize=10,
            fillColor=INK,
        )
    )
    return drawing


def _page_decorator(content: ReportContent) -> Any:
    header_left = plain_text(content.school_name)
    header_right = plain_text(f"{content.title} · {content.exam_name}")
    stamp = content.generated_at.strftime("%d %b %Y %H:%M")
    footer = plain_text(content.footer)

    def _draw(canvas: Any, doc: Any) -> None:
        page_w, page_h = doc.pagesize
        canvas.saveState()
        canvas.setFillColor(BRAND)
        canvas.rect(0, page_h - 6 * mm, page_w, 6 * mm, stroke=0, fill=1)
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN, page_h - 11 * mm, header_left)
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(page_w - MARGIN, page_h - 11 * mm, header_right)
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 12 * mm, page_w - MARGIN, 12 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(MARGIN, 8 * mm, footer)
        canvas.drawRightString(
            page_w - MARGIN, 8 * mm, f"Generated {stamp} · Page {canvas.getPageNumber()}"
        )
        canvas.restoreState()

    return _draw


def render_pdf(content: ReportContent, path: Path) -> None:
    """Write ``content`` as a PDF to ``path``."""
    max_columns = max(
        (
            len(t.columns)
            for s in content.sections
            if s.in_pdf
            for t in s.tables
            if t.in_pdf and t.rows
        ),
        default=0,
    )
    pagesize = landscape(A4) if max_columns >= LANDSCAPE_MIN_COLUMNS else A4
    doc = SimpleDocTemplate(
        str(path),
        pagesize=pagesize,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=content.title,
        author="EduGuardian AI",
        subject=content.subtitle,
    )
    width = pagesize[0] - 2 * MARGIN
    styles = _Styles()
    story: list[Flowable] = [
        Paragraph(safe_text(content.title), styles.title),
        Paragraph(
            safe_text(
                f"{content.school_name} · {content.subtitle} · generated "
                f"{content.generated_at.strftime('%d %b %Y')}"
            ),
            styles.subtitle,
        ),
    ]
    grid = _figures_grid(content, styles, width)
    if grid is not None:
        story += [grid, Spacer(1, 8)]
    if content.narrative:
        story.append(Paragraph("Key findings", styles.h2))
        story += [
            Paragraph(safe_text(line), styles.bullet, bulletText="•") for line in content.narrative
        ]
    for section in content.sections:
        if not section.in_pdf:
            continue
        block: list[Flowable] = [Paragraph(safe_text(section.title), styles.h2)]
        block += [Paragraph(safe_text(p), styles.body) for p in section.paragraphs]
        block += [Paragraph(safe_text(b), styles.bullet, bulletText="•") for b in section.bullets]
        story.append(KeepTogether(block) if len(block) < 6 else block[0])
        if len(block) >= 6:
            story += block[1:]
        if section.chart is not None and section.chart.values:
            story += [Spacer(1, 4), _chart(section.chart, width), Spacer(1, 4)]
        for table in section.tables:
            if table.in_pdf:
                story += _table_flowables(table, styles, width)
                story.append(Spacer(1, 6))
    decorate = _page_decorator(content)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    logger.info("PDF report written: %s (%d bytes)", path, path.stat().st_size)
