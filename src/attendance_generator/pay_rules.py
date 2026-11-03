"""Split of worked time into pay-rate columns for Type A reports.

Type A shows, for every day, how many hours fall into 100%, 125%, 150% and
Saturday ("שבת"). The sample reports prove only part of the rule, so each
piece below is labelled:

    VERIFIED on the samples
        * Saturday work is listed only in the Saturday column.
        * Work on the holiday Simchat Torah (17/10/2022) is listed only in the
          150% column.
        * Every other day (Friday included) is listed in the 100% column.
        * The row total equals 100% + 125% + 150% + Saturday.

    ASSUMED (approved by the project owner, not seen in the samples)
        * On a regular day, the first ``regular_day_minutes`` are 100%, the next
          ``tier_125_minutes`` are 125%, and the rest are 150%.
        * The thresholds apply to NET time (after the break is removed).
        * A long Saturday or holiday stays entirely in its own column.
        * A shift is classified by the date on which it starts, even if it
          passes midnight.

The thresholds are parameters (``PayRules``) so they can change without
touching the logic.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from enum import Enum

from .synthetic_models import SyntheticReportA, TypeADay

SATURDAY_WEEKDAY = 5  # datetime.date.weekday(): Monday = 0 ... Saturday = 5


class DayKind(str, Enum):
    REGULAR = "regular"
    SATURDAY = "saturday"
    HOLIDAY = "holiday"


def _require_positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


@dataclass(frozen=True)
class PayRules:
    """Thresholds, in minutes, for overtime on a regular day (assumed)."""

    regular_day_minutes: int = 8 * 60
    tier_125_minutes: int = 2 * 60

    def __post_init__(self) -> None:
        _require_positive_int(self.regular_day_minutes, "regular_day_minutes")
        _require_positive_int(self.tier_125_minutes, "tier_125_minutes")


DEFAULT_RULES = PayRules()


@dataclass(frozen=True)
class RateSplit:
    """Minutes in each pay column. Always adds up to the time that was split."""

    minutes_100: int = 0
    minutes_125: int = 0
    minutes_150: int = 0
    minutes_saturday: int = 0

    def __post_init__(self) -> None:
        for name in ("minutes_100", "minutes_125", "minutes_150", "minutes_saturday"):
            value = getattr(self, name)

            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")

    @property
    def total_minutes(self) -> int:
        return (
            self.minutes_100
            + self.minutes_125
            + self.minutes_150
            + self.minutes_saturday
        )

    def __add__(self, other: "RateSplit") -> "RateSplit":
        if not isinstance(other, RateSplit):
            return NotImplemented

        return RateSplit(
            self.minutes_100 + other.minutes_100,
            self.minutes_125 + other.minutes_125,
            self.minutes_150 + other.minutes_150,
            self.minutes_saturday + other.minutes_saturday,
        )


def classify_day(work_date: date, holidays: Collection[date] = ()) -> DayKind:
    """Saturday wins over holiday; anything else is regular (Friday too)."""
    if work_date.weekday() == SATURDAY_WEEKDAY:
        return DayKind.SATURDAY

    if work_date in holidays:
        return DayKind.HOLIDAY

    return DayKind.REGULAR


def split_minutes(
    net_minutes: int, kind: DayKind, rules: PayRules = DEFAULT_RULES
) -> RateSplit:
    """Distribute one day's net minutes over the pay columns."""
    if isinstance(net_minutes, bool) or not isinstance(net_minutes, int) or net_minutes < 0:
        raise ValueError("net_minutes must be a non-negative integer.")

    if kind is DayKind.SATURDAY:
        return RateSplit(minutes_saturday=net_minutes)

    if kind is DayKind.HOLIDAY:
        return RateSplit(minutes_150=net_minutes)

    regular = min(net_minutes, rules.regular_day_minutes)
    remaining = net_minutes - regular
    tier_125 = min(remaining, rules.tier_125_minutes)

    return RateSplit(
        minutes_100=regular,
        minutes_125=tier_125,
        minutes_150=remaining - tier_125,
    )


def split_type_a_day(
    day: TypeADay,
    holidays: Collection[date] = (),
    rules: PayRules = DEFAULT_RULES,
) -> RateSplit:
    kind = classify_day(day.work_date, holidays)
    return split_minutes(day.net_minutes, kind, rules)


def total_rate_split(
    report: SyntheticReportA,
    holidays: Collection[date] = (),
    rules: PayRules = DEFAULT_RULES,
) -> RateSplit:
    """Column totals for the summary box; always calculated from the rows."""
    total = RateSplit()

    for day in report.days:
        total = total + split_type_a_day(day, holidays, rules)

    return total
