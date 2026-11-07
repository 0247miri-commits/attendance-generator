"""Generation profile: the "recipe" for one synthetic report (ADR-006).

A profile does not contain days or hours of a particular month. It describes
the *pattern* of one fictitious employee: which weekdays are worked, the usual
entry time and shift length, how much they vary, and how often there are long
days. The generator turns a profile plus a calendar month into daily rows.

Every report gets its own profile (decision: one profile per report). For now a
profile is drawn at random inside ranges anchored to the four sample reports;
later it can also be built from the pattern observed in an extracted source
report (``work_profile.py``) once the parsers exist.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .models import ReportType
from .synthetic_models import MAX_SHIFT_MINUTES
from .units import MINUTES_PER_DAY

# date.weekday(): Monday = 0 ... Sunday = 6
FRIDAY = 4
SATURDAY = 5


def _require_probability(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number between 0 and 1.")

    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1.")


def _require_int_between(value: object, name: str, low: int, high: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")

    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}.")


@dataclass(frozen=True)
class GenerationProfile:
    # Chance that a given weekday is worked. Index 0 = Monday ... 6 = Sunday.
    weekday_work_probability: tuple[float, ...]
    start_minute_center: int
    start_jitter_minutes: int
    duration_minutes_center: int  # gross shift length (includes the break)
    duration_jitter_minutes: int
    granularity_minutes: int  # all times are multiples of this (15 for Type A)
    break_minutes: int = 0  # Type A only
    overtime_probability: float = 0.0  # Type A only: chance of a long day
    overtime_extra_range_minutes: tuple[int, int] = (30, 240)
    holiday_work_probability: float = 0.0  # Type A only
    hourly_rate_agorot: int | None = None  # Type B only

    def __post_init__(self) -> None:
        probabilities = self.weekday_work_probability

        if not isinstance(probabilities, tuple) or len(probabilities) != 7:
            raise ValueError("weekday_work_probability needs exactly 7 values.")

        for index, value in enumerate(probabilities):
            _require_probability(value, f"weekday_work_probability[{index}]")

        _require_probability(self.overtime_probability, "overtime_probability")
        _require_probability(self.holiday_work_probability, "holiday_work_probability")

        _require_int_between(self.start_minute_center, "start_minute_center", 0, MINUTES_PER_DAY - 1)
        _require_int_between(self.start_jitter_minutes, "start_jitter_minutes", 0, 240)
        _require_int_between(self.duration_minutes_center, "duration_minutes_center", 1, MAX_SHIFT_MINUTES)
        _require_int_between(self.duration_jitter_minutes, "duration_jitter_minutes", 0, 240)
        _require_int_between(self.granularity_minutes, "granularity_minutes", 1, 60)
        _require_int_between(self.break_minutes, "break_minutes", 0, 240)

        low, high = self.overtime_extra_range_minutes
        _require_int_between(low, "overtime_extra_range_minutes[0]", 1, 600)
        _require_int_between(high, "overtime_extra_range_minutes[1]", low, 600)

        if self.hourly_rate_agorot is not None:
            _require_int_between(self.hourly_rate_agorot, "hourly_rate_agorot", 1, 100_000)


def sample_profile(rng: random.Random, report_type: ReportType) -> GenerationProfile:
    """Draw a plausible profile. Ranges are anchored to the sample reports.

    The long-day probability is drawn per report between 0% and 40%, so a
    corpus contains reports with no overtime at all, a little, and a lot.
    """
    if report_type is ReportType.TYPE_A:
        working_days = round(rng.uniform(0.55, 0.95), 2)
        friday = rng.choice((0.0, 0.3, 0.9))
        saturday = rng.choice((0.0, 0.0, 0.15, 0.3))

        return GenerationProfile(
            weekday_work_probability=(
                working_days, working_days, working_days, working_days,
                friday, saturday, working_days,
            ),
            start_minute_center=rng.choice(range(7 * 60, 9 * 60 + 1, 30)),
            start_jitter_minutes=rng.choice((0, 30, 60)),
            duration_minutes_center=rng.choice(range(6 * 60 + 30, 9 * 60 + 1, 30)),
            duration_jitter_minutes=rng.choice((0, 30, 60)),
            granularity_minutes=15,
            break_minutes=30,
            overtime_probability=round(rng.uniform(0.0, 0.4), 2),
            holiday_work_probability=rng.choice((0.0, 0.3)),
        )

    if report_type is ReportType.TYPE_B:
        working_days = round(rng.uniform(0.5, 0.95), 2)
        friday = rng.choice((0.0, 0.3, 0.9))

        return GenerationProfile(
            weekday_work_probability=(
                working_days, working_days, working_days, working_days,
                friday, 0.0, working_days,
            ),
            start_minute_center=rng.choice(range(7 * 60 + 30, 9 * 60 + 31, 30)),
            start_jitter_minutes=rng.choice((0, 5, 10)),
            duration_minutes_center=rng.choice(range(150, 301, 30)),
            duration_jitter_minutes=rng.choice((0, 5, 10)),
            granularity_minutes=1,
            hourly_rate_agorot=5 * rng.randint(580, 800),  # 29.00 - 40.00 NIS
        )

    raise ValueError("A profile can only be drawn for Type A or Type B.")
