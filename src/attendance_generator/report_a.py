
"""Data models for attendance report Type A."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class TypeADailyRow:
    """One daily row in a Type A attendance report."""

    work_date: date
    weekday: str | None = None
    workplace: str | None = None
    entry_time: str | None = None
    exit_time: str | None = None

    # Original displayed values.
    # Their exact units and calculation rules are not yet verified.
    break_value: str | None = None
    total_value: str | None = None
    hours_100: str | None = None
    hours_125: str | None = None
    hours_150: str | None = None
    saturday_value: str | None = None


@dataclass(frozen=True)
class TypeASummary:
    """Summary values displayed in a Type A report."""

    workdays_value: str | None = None
    total_hours_value: str | None = None
    hours_100_value: str | None = None
    hours_125_value: str | None = None
    hours_150_value: str | None = None
    saturday_value: str | None = None
    bonus_value: str | None = None
    travel_value: str | None = None


@dataclass(frozen=True)
class TypeAReport:
    """Complete structured representation of a Type A report."""

    source_file: str
    rows: tuple[TypeADailyRow, ...] = ()
    summary: TypeASummary = field(default_factory=TypeASummary)
    synthetic_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_file.strip():
            raise ValueError("Source file cannot be empty.")
