
"""Data models for attendance report Type B."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


def validate_decimal(value: Decimal | None, field_name: str) -> None:
    """Validate a decimal value without converting or rounding it."""
    if value is None:
        return

    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be a Decimal.")

    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")


@dataclass(frozen=True)
class TypeBDailyRow:
    """One calendar-day row in a Type B attendance report."""

    work_date: date
    entry_time: str | None = None
    exit_time: str | None = None
    total_hours: Decimal | None = None
    comments: str | None = None

    def __post_init__(self) -> None:
        validate_decimal(self.total_hours, "total_hours")


@dataclass(frozen=True)
class TypeBSummary:
    """Summary values printed at the top of a Type B report."""

    reported_workdays: int | None = None
    reported_total_hours: Decimal | None = None
    hourly_rate: Decimal | None = None
    reported_total_payment: Decimal | None = None

    def __post_init__(self) -> None:
        if self.reported_workdays is not None:
            if (
                not isinstance(self.reported_workdays, int)
                or isinstance(self.reported_workdays, bool)
                or self.reported_workdays < 0
            ):
                raise ValueError(
                    "reported_workdays must be a non-negative integer."
                )

        validate_decimal(
            self.reported_total_hours, "reported_total_hours"
        )
        validate_decimal(self.hourly_rate, "hourly_rate")
        validate_decimal(
            self.reported_total_payment, "reported_total_payment"
        )


@dataclass(frozen=True)
class TypeBReport:
    """Complete structured representation of a Type B report."""

    source_file: str
    rows: tuple[TypeBDailyRow, ...] = ()
    summary: TypeBSummary = field(default_factory=TypeBSummary)
    synthetic_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_file.strip():
            raise ValueError("Source file cannot be empty.")
