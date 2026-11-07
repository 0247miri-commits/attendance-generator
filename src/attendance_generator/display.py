"""What is PRINTED in a report: one source of truth for PDF and JSON.

The synthetic models hold canonical values (minutes, agorot). This module turns
them into the exact strings shown in each report type, so the PDF renderer and
the JSON "printed" section can never disagree.

Formats below are VERIFIED on the sample reports unless marked ASSUMED.

Type A: date ``01/02/2023``; weekday ``יום רביעי`` but Saturday is just
        ``שבת``; times ``08:00``; break ``00:30``; hours with two decimals;
        totals row has the day count, the break total as HH:MM and the column
        sums; the summary box shows numbers without trailing zeros.
Type B: date ``1/1/23``; weekday ``ראשון`` (no "יום"); times ``8:01``;
        hours with two decimals; month label ``ינו-23``.
ASSUMED: the Hebrew month abbreviations other than ינו (Jan) and ספט (Sep),
        which are the only two seen in the samples.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

from .pay_rules import DEFAULT_RULES, PayRules, split_type_a_day, total_rate_split
from .synthetic_models import SyntheticReportA, SyntheticReportB, summarize_a, summarize_b
from .units import format_clock, format_money, minutes_to_decimal_hours

_SATURDAY = 5  # date.weekday()

# Index = date.weekday() (Monday = 0).
HEBREW_WEEKDAYS = ("שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון")

HEBREW_MONTH_ABBREVIATIONS = {
    1: "ינו", 2: "פבר", 3: "מרץ", 4: "אפר", 5: "מאי", 6: "יונ",
    7: "יול", 8: "אוג", 9: "ספט", 10: "אוק", 11: "נוב", 12: "דצמ",
}


def _hours(minutes: int) -> str:
    """Decimal hours with two digits: 390 -> '6.50'."""
    return f"{minutes_to_decimal_hours(minutes):.2f}"


def _trimmed_hours(minutes: int) -> str:
    """Decimal hours without trailing zeros: 6630 -> '110.5', 0 -> '0'."""
    return format(minutes_to_decimal_hours(minutes).normalize(), "f")


def _total_hhmm(minutes: int) -> str:
    """A total as HH:MM that never wraps at 24 hours: 450 -> '07:30'."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# --------------------------------------------------------------------------- #
# Type B
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PrintedRowB:
    date: str
    weekday: str
    start: str
    end: str
    hours: str
    note: str
    is_saturday: bool


@dataclass(frozen=True)
class PrintedReportB:
    employee_name: str
    work_days: str
    total_hours: str
    hourly_rate: str
    total_pay: str
    month_label: str
    rows: tuple[PrintedRowB, ...]


def print_type_b(report: SyntheticReportB) -> PrintedReportB:
    summary = summarize_b(report)
    rows = []

    for day in report.days:
        current = day.work_date
        worked = day.is_work_day

        rows.append(
            PrintedRowB(
                date=f"{current.day}/{current.month}/{current.year % 100:02d}",
                weekday=HEBREW_WEEKDAYS[current.weekday()],
                start=format_clock(day.shift.start_minute, zero_pad_hour=False) if worked else "",
                end=format_clock(day.shift.end_minute, zero_pad_hour=False) if worked else "",
                hours=_hours(day.minutes) if worked else "",
                note=day.note,
                is_saturday=current.weekday() == _SATURDAY,
            )
        )

    meta = report.metadata

    return PrintedReportB(
        employee_name=report.employee.name,
        work_days=str(summary.work_days),
        total_hours=f"{summary.total_hours:.2f}",
        hourly_rate=format_money(summary.hourly_rate_agorot),
        total_pay=format_money(summary.total_pay_agorot),
        month_label=f"{HEBREW_MONTH_ABBREVIATIONS[meta.month]}-{meta.year % 100:02d}",
        rows=tuple(rows),
    )


# --------------------------------------------------------------------------- #
# Type A
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PrintedRowA:
    date: str
    weekday: str
    workplace: str
    start: str
    end: str
    break_time: str
    total: str
    hours_100: str
    hours_125: str
    hours_150: str
    saturday: str
    is_saturday: bool


@dataclass(frozen=True)
class PrintedTotalsA:
    days: str
    break_total: str
    total: str
    hours_100: str
    hours_125: str
    hours_150: str
    saturday: str


@dataclass(frozen=True)
class PrintedSummaryBoxA:
    days: str
    total_hours: str
    hours_100: str
    hours_125: str
    hours_150: str
    saturday: str
    bonus: str
    travel: str


@dataclass(frozen=True)
class PrintedReportA:
    company_name: str
    rows: tuple[PrintedRowA, ...]
    totals: PrintedTotalsA
    summary_box: PrintedSummaryBoxA


def print_type_a(
    report: SyntheticReportA,
    holidays: Collection[date] = (),
    rules: PayRules = DEFAULT_RULES,
) -> PrintedReportA:
    rows = []

    for day in report.days:
        current = day.work_date
        split = split_type_a_day(day, holidays, rules)
        is_saturday = current.weekday() == _SATURDAY
        weekday = HEBREW_WEEKDAYS[current.weekday()]

        rows.append(
            PrintedRowA(
                date=f"{current:%d/%m/%Y}",
                weekday=weekday if is_saturday else f"יום {weekday}",
                workplace=day.workplace,
                start=format_clock(day.shift.start_minute),
                end=format_clock(day.shift.end_minute),
                break_time=format_clock(day.break_minutes),
                total=_hours(day.net_minutes),
                hours_100=_hours(split.minutes_100),
                hours_125=_hours(split.minutes_125),
                hours_150=_hours(split.minutes_150),
                saturday=_hours(split.minutes_saturday),
                is_saturday=is_saturday,
            )
        )

    summary = summarize_a(report)
    split_total = total_rate_split(report, holidays, rules)

    # Column totals come from exact minutes and are rounded once (ASSUMED for
    # Type A; harmless while all times are multiples of 15 minutes).
    totals = PrintedTotalsA(
        days=str(summary.work_days),
        break_total=_total_hhmm(summary.total_break_minutes),
        total=_hours(summary.total_net_minutes),
        hours_100=_hours(split_total.minutes_100),
        hours_125=_hours(split_total.minutes_125),
        hours_150=_hours(split_total.minutes_150),
        saturday=_hours(split_total.minutes_saturday),
    )

    box = PrintedSummaryBoxA(
        days=str(summary.work_days),
        total_hours=_trimmed_hours(summary.total_net_minutes),
        hours_100=_trimmed_hours(split_total.minutes_100),
        hours_125=_trimmed_hours(split_total.minutes_125),
        hours_150=_trimmed_hours(split_total.minutes_150),
        saturday=_trimmed_hours(split_total.minutes_saturday),
        bonus="0",  # always 0 in the samples; not modelled
        travel="0",
    )

    return PrintedReportA(report.company_name, tuple(rows), totals, box)
