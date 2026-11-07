"""PDF renderer for Type B: the monthly employee card (כרטיס עובד לחודש).

The page is drawn from the strings produced by ``display.py`` so that it always
agrees with the JSON export. Geometry (in points, measured from the TOP of an
A4 page) was measured on the January 2023 sample scan:

    * six columns with the measured edges below,
    * a two-line table header 27.2 pt high and body rows 12.75 pt high,
    * a name box, a four-row summary box and a month label above the table,
    * Saturday rows shaded grey (all columns except the notes column).
"""

from __future__ import annotations

from pathlib import Path

from .display import PrintedReportB, print_type_b
from .pdf_common import Page, baseline_for, new_canvas
from .synthetic_models import SyntheticReportB

# Column edges from right to left: date, weekday, entry, exit, hours, notes.
COLUMN_EDGES = (432.0, 380.9, 330.0, 279.8, 222.7, 170.4, 119.3)
TABLE_LEFT = COLUMN_EDGES[-1]
TABLE_RIGHT = COLUMN_EDGES[0]

HEADER_TOP = 258.0
HEADER_BOTTOM = 285.2
ROW_HEIGHT = 12.75

TEXT_SIZE = 10.8
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


def _draw_header_boxes(page: Page, printed: PrintedReportB) -> None:
    size = TEXT_SIZE
    name_baseline = baseline_for(135.5, 152.5, size)

    # Name box: two rows, the first grey with the label and the name.
    page.box(224.5, 135.5, 385.4, 152.5, gray=GREY)
    page.line(334.6, 135.5, 334.6, 152.5)
    page.box(224.5, 152.5, 385.4, 166.0)
    page.text("שם העובד:", 334.6, 385.4, name_baseline, size=size, bold=True)
    page.text(printed.employee_name, 224.5, 334.6, name_baseline, size=size, bold=True)

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
        baseline = baseline_for(y0, y1, size)
        page.text(label, split, label_right, baseline, size=size, bold=True, align="right", pad=4)

        if is_money:
            page.text("₪", value_left, split, baseline, size=size, bold=True, align="left", pad=3)
            page.text(value, value_left, split, baseline, size=size, bold=True, align="right", pad=3)
        else:
            page.text(value, value_left, split, baseline, size=size, bold=True)

    # Month label.
    month_baseline = baseline_for(232.0, 246.0, size)
    page.box(281.0, 232.0, 383.3, 246.0, gray=GREY)
    page.box(171.5, 232.0, 281.0, 246.0, gray=GREY)
    page.text("כרטיס עובד לחודש:", 281.0, 383.3, month_baseline, size=size, bold=True, align="right", pad=4)
    page.text(printed.month_label, 171.5, 281.0, month_baseline, size=size, bold=True)


def _draw_table(page: Page, printed: PrintedReportB) -> None:
    rows = printed.rows
    bottom = HEADER_BOTTOM + len(rows) * ROW_HEIGHT
    size = TEXT_SIZE

    # Shade Saturday rows (every column except notes) before the grid.
    for index, row in enumerate(rows):
        if row.is_saturday:
            y0 = HEADER_BOTTOM + index * ROW_HEIGHT
            page.fill(COLUMN_EDGES[4], y0, COLUMN_EDGES[0], y0 + ROW_HEIGHT, GREY)

    # Header texts.
    for column, (lines, placement) in enumerate(HEADER_CELLS):
        x1, x0 = COLUMN_EDGES[column], COLUMN_EDGES[column + 1]

        if placement == "two":
            page.text(lines[0], x0, x1, HEADER_TOP + 11.0, size=size, bold=True)
            page.text(lines[1], x0, x1, HEADER_BOTTOM - 3.5, size=size, bold=True)
        elif placement == "bottom":
            page.text(lines[0], x0, x1, HEADER_BOTTOM - 3.5, size=size, bold=True)
        else:
            page.text(lines[0], x0, x1, HEADER_TOP + 10.0, size=size, bold=True)

    # Body texts.
    for index, row in enumerate(rows):
        y0 = HEADER_BOTTOM + index * ROW_HEIGHT
        baseline = baseline_for(y0, y0 + ROW_HEIGHT, size)
        values = (row.date, row.weekday, row.start, row.end, row.hours)

        for column, value in enumerate(values):
            page.text(value, COLUMN_EDGES[column + 1], COLUMN_EDGES[column], baseline, size=size, bold=True)

        page.text(row.note, COLUMN_EDGES[6], COLUMN_EDGES[5], baseline, size=size, bold=True, align="right")

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
    printed = print_type_b(report)
    page = Page(new_canvas(path, kind="B", metadata=report.metadata))

    _draw_header_boxes(page, printed)
    _draw_table(page, printed)
    page.save()
    return Path(path)
