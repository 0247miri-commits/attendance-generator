"""PDF renderer for Type A: the staffing-company attendance report.

Geometry (points, measured from the TOP of an A4 page) comes from the October
2022 sample scan:

    * a company title and an employee line, right aligned above the table,
    * a header strip with ruled cells but NO grid lines in the body,
    * 11 columns; all text is right aligned inside its cell, 3 pt from the
      cell's right edge, except the header of the numeric columns (centred),
    * a totals row directly under the last day,
    * an eight-row summary box (days, hours, 100/125/150, Saturday, bonus,
      travel) under the table, aligned to the right edge.

The "מקום עבודה" header is cut by its cell, as in the original.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import date
from pathlib import Path

from .display import PrintedReportA, print_type_a
from .pay_rules import DEFAULT_RULES, PayRules
from .pdf_common import Page, baseline_for, new_canvas
from .synthetic_models import SyntheticReportA

# Column edges from right to left: date, day, workplace, entry, exit, break,
# total, 100%, 125%, 150%, Saturday (11 columns, 12 edges).
EDGES = (529.7, 471.1, 418.8, 380.4, 346.3, 314.6, 273.4, 236.9, 199.0, 161.0, 123.1, 91.4)
PADS = (3.6, 1.5, 3.4, 3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 3.2)
HEADER_LABELS = ("תאריך", "יום", "מקום עבודה", "כניסה", "יציאה", "הפסקה", 'סה"כ', "100%", "125%", "150%", "שבת")
RIGHT_ALIGNED_HEADERS = 3  # the first three header labels are right aligned

HEADER_TOP = 101.3
HEADER_BOTTOM = 116.4
ROW_HEIGHT = 12.96
TEXT_SIZE = 10.5
TITLE_SIZE = 11.5
TITLE_CENTER = 83.0
EMPLOYEE_CENTER = 94.5
GREY = 0.6

BOX_LEFT, BOX_DIVIDER, BOX_RIGHT = 418.8, 471.1, 529.7
BOX_ROW = 12.95

RIGHT_EDGE = EDGES[0]


def _draw_title(page: Page, printed: PrintedReportA, employee_name: str) -> None:
    page.text(
        printed.company_name, EDGES[-1], RIGHT_EDGE,
        baseline_for(TITLE_CENTER - 6, TITLE_CENTER + 6, TITLE_SIZE),
        size=TITLE_SIZE, align="right", pad=2.0,
    )
    page.text(
        employee_name, EDGES[-1], RIGHT_EDGE,
        baseline_for(EMPLOYEE_CENTER - 5, EMPLOYEE_CENTER + 5, TEXT_SIZE),
        size=TEXT_SIZE, align="right", pad=2.0,
    )


def _draw_header(page: Page) -> None:
    baseline = baseline_for(HEADER_TOP, HEADER_BOTTOM, TEXT_SIZE)

    # The "יום" header cell is shaded.
    page.fill(EDGES[2], HEADER_TOP, EDGES[1], HEADER_BOTTOM, GREY)

    for column, label in enumerate(HEADER_LABELS):
        x1, x0 = EDGES[column], EDGES[column + 1]

        if column < RIGHT_ALIGNED_HEADERS:
            with page.clipped(x0, HEADER_TOP, x1, HEADER_BOTTOM):
                page.text(label, x0, x1, baseline, size=TEXT_SIZE, bold=True, align="right", pad=PADS[column])
        else:
            page.text(label, x0, x1, baseline, size=TEXT_SIZE, bold=True)

    page.line(EDGES[-1], HEADER_TOP, EDGES[0], HEADER_TOP, 1.4)

    for edge in EDGES:
        page.line(edge, HEADER_TOP, edge, HEADER_BOTTOM)


def _row_values(row) -> tuple[str, ...]:
    return (
        row.date, row.weekday, row.workplace, row.start, row.end, row.break_time,
        row.total, row.hours_100, row.hours_125, row.hours_150, row.saturday,
    )


def _draw_rows(page: Page, printed: PrintedReportA) -> float:
    """Draw the day rows and the totals row; return the bottom of the totals row."""
    for index, row in enumerate(printed.rows):
        top = HEADER_BOTTOM + index * ROW_HEIGHT
        baseline = baseline_for(top, top + ROW_HEIGHT, TEXT_SIZE)

        if row.is_saturday:  # only the weekday cell is shaded
            page.fill(EDGES[2], top + 1.0, EDGES[1], top + ROW_HEIGHT - 1.0, GREY)

        for column, value in enumerate(_row_values(row)):
            page.text(value, EDGES[column + 1], EDGES[column], baseline, size=TEXT_SIZE, align="right", pad=PADS[column])

    totals = printed.totals
    top = HEADER_BOTTOM + len(printed.rows) * ROW_HEIGHT
    baseline = baseline_for(top, top + ROW_HEIGHT, TEXT_SIZE)
    cells = {
        0: totals.days, 5: totals.break_total, 6: totals.total,
        7: totals.hours_100, 8: totals.hours_125, 9: totals.hours_150, 10: totals.saturday,
    }

    for column, value in cells.items():
        page.text(value, EDGES[column + 1], EDGES[column], baseline, size=TEXT_SIZE, align="right", pad=PADS[column])

    return top + ROW_HEIGHT


def _draw_summary_box(page: Page, printed: PrintedReportA, top: float) -> None:
    box = printed.summary_box
    rows = (
        ("ימים", box.days),
        ('סה"כ שעות', box.total_hours),
        ("שעות 100%", box.hours_100),
        ("שעות 125%", box.hours_125),
        ("שעות 150%", box.hours_150),
        ("שבת 150%", box.saturday),
        ("בונוס", box.bonus),
        ("נסיעות", box.travel),
    )

    for index, (label, value) in enumerate(rows):
        y0, y1 = top + index * BOX_ROW, top + (index + 1) * BOX_ROW
        baseline = baseline_for(y0, y1, TEXT_SIZE)
        page.box(BOX_LEFT, y0, BOX_DIVIDER, y1)
        page.box(BOX_DIVIDER, y0, BOX_RIGHT, y1)
        page.text(value, BOX_LEFT, BOX_DIVIDER, baseline, size=TEXT_SIZE, align="right", pad=3.0)
        page.text(label, BOX_DIVIDER, BOX_RIGHT, baseline, size=TEXT_SIZE, align="right", pad=3.0)


def render_type_a(
    report: SyntheticReportA,
    path: Path,
    holidays: Collection[date] = (),
    rules: PayRules = DEFAULT_RULES,
) -> Path:
    """Write the report as a one-page PDF and return its path."""
    printed = print_type_a(report, holidays, rules)
    page = Page(new_canvas(path, kind="A", metadata=report.metadata))

    _draw_title(page, printed, report.employee.name)
    _draw_header(page)
    totals_bottom = _draw_rows(page, printed)
    _draw_summary_box(page, printed, totals_bottom - 0.7)
    page.save()
    return Path(path)
