"""Data models for SYNTHETIC (generated) attendance reports.

These models are deliberately separate from ``models.py`` / ``report_a.py`` /
``report_b.py``, which describe data *extracted* from a source document
(ADR-002). Here every value is canonical:

    * times are ints (minutes after midnight of the work date),
    * money is an int (agorot),
    * nothing is stored that can be derived (weekday, totals, summaries).

Display formatting (``08:05`` vs ``8:05``, ``3.07``) belongs to the renderer.

Shifts that pass midnight (night shifts) are supported: ``end_minute`` may be
larger than 1440. A shift 22:00-06:00 is ``start=1320, end=1800``. The shift
belongs to the date on which it STARTS (an assumption, to be confirmed).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import ReportType
from .units import MINUTES_PER_DAY, minutes_to_decimal_hours, pay_agorot

# Assumption, not taken from the sample reports: no single shift is longer.
MAX_SHIFT_MINUTES = 16 * 60


def _require_int(value: object, name: str, *, minimum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int.")

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")


def _require_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} cannot be empty.")


# --------------------------------------------------------------------------- #
# Shared building blocks (composition, not inheritance)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SyntheticEmployee:
    """A fictitious employee. Nothing here comes from a source report."""

    name: str
    employee_id: str

    def __post_init__(self) -> None:
        _require_text(self.name, "Employee name")
        _require_text(self.employee_id, "Employee id")


@dataclass(frozen=True)
class ReportMetadata:
    """What is needed to identify and reproduce one generated report."""

    report_type: ReportType
    year: int
    month: int
    seed: int
    generator_version: str

    def __post_init__(self) -> None:
        if self.report_type not in (ReportType.TYPE_A, ReportType.TYPE_B):
            raise ValueError("Report type must be TYPE_A or TYPE_B.")

        _require_int(self.year, "year")
        _require_int(self.month, "month")
        _require_int(self.seed, "seed")
        _require_text(self.generator_version, "Generator version")

        if not 1900 <= self.year <= 2100:
            raise ValueError("Year must be between 1900 and 2100.")

        if not 1 <= self.month <= 12:
            raise ValueError("Month must be between 1 and 12.")

    @property
    def is_synthetic(self) -> bool:
        """Always True; used when marking JSON and PDF output."""
        return True

    @property
    def days_in_month(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]


@dataclass(frozen=True)
class WorkShift:
    """Entry and exit, in minutes after midnight of the shift's start date."""

    start_minute: int
    end_minute: int

    def __post_init__(self) -> None:
        _require_int(self.start_minute, "start_minute")
        _require_int(self.end_minute, "end_minute")

        if not 0 <= self.start_minute < MINUTES_PER_DAY:
            raise ValueError("start_minute must be within a single day (0-1439).")

        if self.end_minute <= self.start_minute:
            raise ValueError(
                "end_minute must be after start_minute. For a shift that "
                "passes midnight use end_minute greater than 1440."
            )

        if self.end_minute - self.start_minute > MAX_SHIFT_MINUTES:
            raise ValueError("Shift is longer than the allowed maximum.")

    @property
    def duration_minutes(self) -> int:
        return self.end_minute - self.start_minute

    @property
    def crosses_midnight(self) -> bool:
        return self.end_minute > MINUTES_PER_DAY


# --------------------------------------------------------------------------- #
# Daily records - one per report type, because the reports differ (ADR-001)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TypeADay:
    """A day worked in a Type A report. Type A lists worked days only."""

    work_date: date
    workplace: str
    shift: WorkShift
    break_minutes: int = 0

    def __post_init__(self) -> None:
        _require_text(self.workplace, "Workplace")
        _require_int(self.break_minutes, "break_minutes", minimum=0)

        if self.break_minutes >= self.shift.duration_minutes:
            raise ValueError("Break must be shorter than the shift.")

    @property
    def net_minutes(self) -> int:
        """Worked time: exit - entry - break (verified on the samples)."""
        return self.shift.duration_minutes - self.break_minutes


@dataclass(frozen=True)
class TypeBDay:
    """A calendar day in a Type B report. ``shift`` is None on a day off."""

    work_date: date
    shift: WorkShift | None = None
    note: str = ""

    @property
    def is_work_day(self) -> bool:
        return self.shift is not None

    @property
    def minutes(self) -> int:
        return self.shift.duration_minutes if self.shift else 0


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def _check_days_in_month(
    days: tuple, metadata: ReportMetadata, date_attr: str
) -> None:
    if not isinstance(days, tuple):
        raise TypeError("days must be a tuple.")

    previous: date | None = None

    for day in days:
        current = getattr(day, date_attr)

        if (current.year, current.month) != (metadata.year, metadata.month):
            raise ValueError(f"{current} is outside the report month.")

        if previous is not None and current <= previous:
            raise ValueError("Days must be in strictly ascending date order.")

        previous = current


@dataclass(frozen=True)
class SyntheticReportA:
    metadata: ReportMetadata
    employee: SyntheticEmployee
    company_name: str
    days: tuple[TypeADay, ...]

    def __post_init__(self) -> None:
        if self.metadata.report_type is not ReportType.TYPE_A:
            raise ValueError("Metadata does not describe a Type A report.")

        _require_text(self.company_name, "Company name")
        _check_days_in_month(self.days, self.metadata, "work_date")


@dataclass(frozen=True)
class SyntheticReportB:
    metadata: ReportMetadata
    employee: SyntheticEmployee
    hourly_rate_agorot: int
    days: tuple[TypeBDay, ...]

    def __post_init__(self) -> None:
        if self.metadata.report_type is not ReportType.TYPE_B:
            raise ValueError("Metadata does not describe a Type B report.")

        _require_int(self.hourly_rate_agorot, "hourly_rate_agorot", minimum=1)
        _check_days_in_month(self.days, self.metadata, "work_date")

        # Decision 4: every real day of the month, and only those.
        if len(self.days) != self.metadata.days_in_month:
            raise ValueError("A Type B report must contain every day of the month.")


# --------------------------------------------------------------------------- #
# Summaries are calculated, never stored, so they cannot disagree with rows.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SyntheticSummaryA:
    work_days: int
    total_net_minutes: int
    total_break_minutes: int
    # The split into 100% / 125% / 150% / Saturday is added together with the
    # approved pay rules; it is not calculated here on purpose (ADR-008).


@dataclass(frozen=True)
class SyntheticSummaryB:
    work_days: int
    total_minutes: int
    total_hours: Decimal
    hourly_rate_agorot: int
    total_pay_agorot: int


def summarize_a(report: SyntheticReportA) -> SyntheticSummaryA:
    return SyntheticSummaryA(
        work_days=len(report.days),
        total_net_minutes=sum(day.net_minutes for day in report.days),
        total_break_minutes=sum(day.break_minutes for day in report.days),
    )


def summarize_b(report: SyntheticReportB) -> SyntheticSummaryB:
    total_minutes = sum(day.minutes for day in report.days)

    return SyntheticSummaryB(
        work_days=sum(1 for day in report.days if day.is_work_day),
        total_minutes=total_minutes,
        total_hours=minutes_to_decimal_hours(total_minutes),
        hourly_rate_agorot=report.hourly_rate_agorot,
        total_pay_agorot=pay_agorot(total_minutes, report.hourly_rate_agorot),
    )
