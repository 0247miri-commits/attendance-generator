
"""Build work-pattern profiles from extracted attendance reports."""

from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from .report_b import TypeBReport


@dataclass(frozen=True)
class DistributionProfile:
    """Statistical description of observed numeric values."""

    values: tuple[Decimal, ...]

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def minimum(self) -> Decimal | None:
        return min(self.values) if self.values else None

    @property
    def maximum(self) -> Decimal | None:
        return max(self.values) if self.values else None

    @property
    def average(self) -> Decimal | None:
        if not self.values:
            return None

        return sum(self.values, Decimal("0")) / Decimal(len(self.values))

    @property
    def median(self) -> Decimal | None:
        if not self.values:
            return None

        return Decimal(str(median(self.values)))

    @property
    def median_absolute_deviation(self) -> Decimal | None:
        """Measure variability around the median."""
        center = self.median

        if center is None:
            return None

        deviations = tuple(
            abs(value - center) for value in self.values
        )

        return Decimal(str(median(deviations)))


@dataclass(frozen=True)
class WorkProfile:
    """Observed work patterns from one source report."""

    report_type: str
    source_file: str
    observed_workdays: int
    start_times_minutes: DistributionProfile
    daily_hours: DistributionProfile
    weekday_counts: tuple[tuple[int, int], ...]


def parse_time_to_minutes(value: str) -> int:
    """Convert an HH:MM time string into minutes since midnight."""

    try:
        parts = value.split(":")

        if len(parts) != 2:
            raise ValueError

        hours, minutes = map(int, parts)

        if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
            raise ValueError

        return hours * 60 + minutes

    except (ValueError, AttributeError):
        raise ValueError(
            f"Invalid time format: {value!r}. Expected HH:MM."
        ) from None


def build_type_b_profile(report: TypeBReport) -> WorkProfile:
    """
    Build a profile from one Type B report.

    Only observed values are included.
    Missing values are not replaced with zero.
    """

    start_times = []
    daily_hours = []
    weekday_counts: dict[int, int] = {}

    for row in report.rows:
        if row.total_hours is not None:
            daily_hours.append(row.total_hours)
            weekday = row.work_date.weekday()
            weekday_counts[weekday] = (
                weekday_counts.get(weekday, 0) + 1
            )

        if row.entry_time is not None:
            start_times.append(
                Decimal(parse_time_to_minutes(row.entry_time))
            )

    return WorkProfile(
        report_type="type_b",
        source_file=report.source_file,
        observed_workdays=len(daily_hours),
        start_times_minutes=DistributionProfile(
            values=tuple(start_times)
        ),
        daily_hours=DistributionProfile(
            values=tuple(daily_hours)
        ),
        weekday_counts=tuple(sorted(weekday_counts.items())),
    )
