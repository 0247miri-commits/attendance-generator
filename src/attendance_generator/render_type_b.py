"""PDF renderer for Type B: the monthly employee card (כרטיס עובד לחודש).

The page is drawn from the strings produced by ``display.py`` so that it always
agrees with the JSON export. Geometry (in points, measured from the TOP of an
A4 page) was measured on the January 2023 sample scan:

    * six columns with the measured edges below,
    * a two-line table header 27.2 pt high and body rows 12.75 pt high,
    * a name box, a four-row summary box and a month label above the table,
    * Saturday rows shaded grey (all columns except the notes column).

Hebrew is written right-to-left. ReportLab draws glyphs left to right, so any
string containing Hebrew is first reordered with the Unicode bidi algorithm.

The PDF is written with ``invariant=1`` so the same report always gives the
same bytes, and its metadata states that the document is synthetic.
"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

try:  # python-bidi >= 0.5 exposes get_display at the top level
    from bidi import get_display
except ImportError:  # pragma: no cover - older python-bidi
    from bidi.algorithm import get_display

from .display import PrintedReportB, print_type_b
from .paths import FONT_DIR
from .synthetic_models import SyntheticReportB

PAGE_WIDTH, PAGE_HEIGHT = A4

REGULAR = "LiberationSans"
BOLD = "LiberationSans-Bold"

# Column edges from right to left: date, weekday, entry, exit, hours, notes.
COLUMN_EDGES = (432.0, 380.9, 330.0, 279.8, 222.7, 170.4, 119.3)
TABLE_LEFT = COLUMN_EDGES[-1]
TABLE_RIGHT = COLUMN_EDGES[0]

HEADER_TOP = 258.0
HEADER_BOTTOM = 285.2
ROW_HEIGHT = 12.75

BODY_SIZE = 10.8
HEADER_SIZE = 10.8
GRID_WIDTH = 0.8
GREY = 0.85

# (lines of text, vertical placement) for each header cell, right to left.
HEADER_CELLS = (
    (("תאריך",), "bottom"),
    (("יום", "בשבוע"), "two"),
    (("שעת", "כניסה"), "two"),
    (("שעת יציאה",), "bottom"),
    (('סה"כ', "שעות"), "two"),
    (("הערות",), "top"),
)

_HEBREW = re.compile("[֐-׿]")


def _register_fonts() -> None:
    registered = set(pdfmetrics.getRegisteredFontNames())

    for name, filename in ((REGULAR, "LiberationSans-Regular.ttf"), (BOLD, "LiberationSans-Bold.ttf")):
        if name in registered:
            continue

        path = FONT_DIR / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Font file not found: {path}. Copy the Liberation Sans fonts into the 'fonts' folder."
            )

        pdfmetrics.registerFont(TTFont(name, str(path)))


def _visual(text: str) -> str:
    """Reorder text containing Hebrew into drawing (left-to-right) order."""
    return get_display(text) if _HEBREW.search(text) else text


class _Page:
    """Small drawing helper that works in top-based coordinates."""

    def __init__(self, canvas: Canvas) -> None:
        self.canvas = canvas

    def y(self, top: float) -> float:
        return PAGE_HEIGHT - top

    def line(self, x0: float, y0: float, x1: float, y1: float, width: float = GRID_WIDTH) -> None:
        self.canvas.setLineWidth(width)
        self.canvas.line(x0, self.y(y0), x1, self.y(y1))

    def box(self, x0: float, top: float, x1: float, bottom: float, *, grey: bool = False, width: float = GRID_WIDTH) -> None:
        self.canvas.setLineWidth(width)

        if grey:
            self.canvas.setFillGray(GREY)

        self.canvas.rect(x0, self.y(bottom), x1 - x0, bottom - top, stroke=1, fill=1 if grey else 0)
        self.canvas.setFillGray(0)

    def text(
        self, text: str, x0: float, x1: float, baseline_top: float, *,
        size: float = BODY_SIZE, bold: bool = True, align: str = "center", pad: float = 2.5,
    ) -> None:
        if not text:
            return

        font = BOLD if bold else REGULAR
        visual = _visual(text)
        width = self.canvas.stringWidth(visual, font, size)

        if align == "center":
            x = (x0 + x1) / 2 - width / 2
        elif align == "right":
            x = x1 - pad - width
        else:
            x = x0 + pad

        self.canvas.setFont(font, size)
        self.canvas.drawString(x, self.y(baseline_top), visual)


def _baseline(top: float, bottom: float, size: float) -> float:
    """Baseline that vertically centres text between two y positions."""
    return (top + bottom) / 2 + size * 0.34


def _draw_header_boxes(page: _Page, printed: PrintedReportB) -> None:
    # Name box: two rows, the first grey with the label and the name.
    page.box(224.5, 135.5, 385.4, 152.5, grey=True)
    page.line(334.6, 135.5, 334.6, 152.5)
    page.box(224.5, 152.5, 385.4, 166.0)
    page.text("שם העובד:", 334.6, 385.4, _baseline(135.5, 152.5, HEADER_SIZE), size=HEADER_SIZE)
    page.text(printed.employee_name, 224.5, 334.6, _baseline(135.5, 152.5, HEADER_SIZE), size=HEADER_SIZE)

    # Summary box: label cell on the right, value cell on the left.
    value_left, split, label_right = 223.2, 281.7, 435.0
    row = 13.5
    top = 165.5

    rows = (
        ('סה"כ ימי עבודה לחודש', printed.work_days, False),
        ('סה"כ שעות חודשיות', printed.total_hours, False),
        ("מחיר לשעה", printed.hourly_rate, True),
        ('סה"כ לתשלום', printed.total_pay, True),
    )

    for index, (label, value, is_money) in enumerate(rows):
        y0, y1 = top + index * row, top + (index + 1) * row
        page.box(value_left, y0, split, y1)
        page.box(split, y0, label_right, y1)
        baseline = _baseline(y0, y1, HEADER_SIZE)
        page.text(label, split, label_right, baseline, size=HEADER_SIZE, align="right", pad=4)

        if is_money:
            page.text("₪", value_left, split, baseline, size=HEADER_SIZE, align="left", pad=3)
            page.text(value, value_left, split, baseline, size=HEADER_SIZE, align="right", pad=3)
        else:
            page.text(value, value_left, split, baseline, size=HEADER_SIZE)

    # Month label.
    page.box(281.0, 232.0, 383.3, 246.0, grey=True)
    page.box(171.5, 232.0, 281.0, 246.0, grey=True)
    page.text("כרטיס עובד לחודש:", 281.0, 383.3, _baseline(232.0, 246.0, HEADER_SIZE), size=HEADER_SIZE, align="right", pad=4)
    page.text(printed.month_label, 171.5, 281.0, _baseline(232.0, 246.0, HEADER_SIZE), size=HEADER_SIZE)


def _draw_table(page: _Page, printed: PrintedReportB) -> None:
    rows = printed.rows
    bottom = HEADER_BOTTOM + len(rows) * ROW_HEIGHT

    # Shade Saturday rows (every column except notes) before the grid.
    for index, row in enumerate(rows):
        if row.is_saturday:
            y0 = HEADER_BOTTOM + index * ROW_HEIGHT
            page.canvas.setFillGray(GREY)
            page.canvas.rect(COLUMN_EDGES[4], page.y(y0 + ROW_HEIGHT), COLUMN_EDGES[0] - COLUMN_EDGES[4], ROW_HEIGHT, stroke=0, fill=1)
            page.canvas.setFillGray(0)

    # Header texts.
    for column, (lines, placement) in enumerate(HEADER_CELLS):
        x1, x0 = COLUMN_EDGES[column], COLUMN_EDGES[column + 1]

        if placement == "two":
            page.text(lines[0], x0, x1, HEADER_TOP + 11.0, size=HEADER_SIZE)
            page.text(lines[1], x0, x1, HEADER_BOTTOM - 3.5, size=HEADER_SIZE)
        elif placement == "bottom":
            page.text(lines[0], x0, x1, HEADER_BOTTOM - 3.5, size=HEADER_SIZE)
        else:
            page.text(lines[0], x0, x1, HEADER_TOP + 10.0, size=HEADER_SIZE)

    # Body texts.
    for index, row in enumerate(rows):
        y0 = HEADER_BOTTOM + index * ROW_HEIGHT
        baseline = _baseline(y0, y0 + ROW_HEIGHT, BODY_SIZE)
        values = (row.date, row.weekday, row.start, row.end, row.hours)

        for column, value in enumerate(values):
            page.text(value, COLUMN_EDGES[column + 1], COLUMN_EDGES[column], baseline)

        page.text(row.note, COLUMN_EDGES[6], COLUMN_EDGES[5], baseline, align="right")

    # Grid: horizontal lines, vertical lines, thicker outline.
    for index in range(len(rows) + 1):
        y = HEADER_BOTTOM + index * ROW_HEIGHT
        page.line(TABLE_LEFT, y, TABLE_RIGHT, y)

    for edge in COLUMN_EDGES:
        page.line(edge, HEADER_TOP, edge, bottom)

    page.line(TABLE_LEFT, HEADER_TOP, TABLE_RIGHT, HEADER_TOP, 1.4)
    page.line(TABLE_LEFT, HEADER_BOTTOM, TABLE_RIGHT, HEADER_BOTTOM, 1.4)
    page.line(TABLE_LEFT, bottom, TABLE_RIGHT, bottom, 1.4)


def render_type_b(report: SyntheticReportB, path: Path) -> Path:
    """Write the report as a one-page PDF and return its path."""
    _register_fonts()
    printed = print_type_b(report)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    canvas = Canvas(str(path), pagesize=A4, invariant=1)
    meta = report.metadata

    canvas.setTitle(f"Synthetic attendance report (Type B) {meta.year}-{meta.month:02d}")
    canvas.setAuthor("attendance-generator")
    canvas.setSubject("SYNTHETIC DATA: generated for testing, not a real report")
    canvas.setKeywords(f"synthetic; type=B; seed={meta.seed}; generator={meta.generator_version}")
    canvas.setCreator("attendance-generator")

    page = _Page(canvas)
    _draw_header_boxes(page, printed)
    _draw_table(page, printed)
    canvas.showPage()
    canvas.save()
    return path
