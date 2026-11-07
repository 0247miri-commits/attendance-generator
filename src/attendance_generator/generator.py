"""Generate synthetic attendance reports from a seed (deterministic).

The same ``seed`` (and the same generator version and Python version) always
produces the same report, so every report in a corpus can be reproduced.

Flow for one report:
    seed -> random.Random -> profile (drawn, or given) -> which days are
    worked -> entry/exit for each worked day -> a SyntheticReportA/B.

Holidays are an INPUT (a mapping date -> name). Looking holidays up in the
Hebrew calendar is a separate concern, so this module has no calendar
dependency and is easy to test.
"""

from __future__ import annotations

import calendar
import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from . import __version__
from .generation_profile import SATURDAY, GenerationProfile, sample_profile
from .models import ReportType
from .pay_rules import DEFAULT_RULES, PayRules
from .synthetic_models import (
    MAX_SHIFT_MINUTES,
    ReportMetadata,
    SyntheticEmployee,
    SyntheticReportA,
    SyntheticReportB,
    TypeADay,
    TypeBDay,
    WorkShift,
)
from .units import MINUTES_PER_DAY

# Fictitious data only. Nothing here is copied from a source report.
_FIRST_NAMES = ("נועה", "דניאל", "מאיה", "איתי", "שירה", "יונתן", "תמר", "אורי", "ליאור", "רוני")
_LAST_NAMES = ("כהן", "לוי", "מזרחי", "פרידמן", "אברהם", "דוד", "שפירא", "ברק", "אלון", "נחום")
_COMPANIES = (
    'אלפא כוח אדם בע"מ',
    'גמא שירותי תעסוקה בע"מ',
    'דלתא משאבי אנוש בע"מ',
    'סיגמא כוח אדם בע"מ',
)
_WORKPLACES = ("חיפה", "נתניה", "אשדוד", "באר שבע", "רחובות", "כרמיאל")


@dataclass(frozen=True)
class Generated:
    """A report together with the profile it was generated from."""

    profile: GenerationProfile
    report: SyntheticReportA | SyntheticReportB


def _snap(value: int, step: int) -> int:
    """Round to the nearest multiple of ``step`` (integers only)."""
    return ((value + step // 2) // step) * step


def _month_dates(year: int, month: int) -> list[date]:
    days = calendar.monthrange(year, month)[1]
    return [date(year, month, day) for day in range(1, days + 1)]


def _make_employee(rng: random.Random) -> SyntheticEmployee:
    name = f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"
    return SyntheticEmployee(name=name, employee_id=f"S-{rng.randint(10000, 99999)}")


def _decide_working_dates(
    rng: random.Random,
    profile: GenerationProfile,
    dates: list[date],
    holidays: Mapping[date, str],
    *,
    holiday_blocks_work: bool,
) -> list[date]:
    """Choose which days are worked. Never returns an empty list."""
    working: list[date] = []

    for current in dates:
        # A holiday that falls on Saturday is treated as Saturday.
        is_holiday = current in holidays and current.weekday() != SATURDAY

        if is_holiday:
            probability = 0.0 if holiday_blocks_work else profile.holiday_work_probability
        else:
            probability = profile.weekday_work_probability[current.weekday()]

        if rng.random() < probability:
            working.append(current)

    if not working:
        # An empty report is not plausible: work the first usable day.
        fallback = next(
            (d for d in dates
             if d not in holidays and profile.weekday_work_probability[d.weekday()] > 0),
            next((d for d in dates if d not in holidays), dates[0]),
        )
        working.append(fallback)

    return working


def _draw_shift(
    rng: random.Random, profile: GenerationProfile, *, min_duration: int
) -> tuple[int, int]:
    """Return (start_minute, gross_duration) following the profile."""
    step = profile.granularity_minutes

    start = _snap(
        profile.start_minute_center
        + rng.randint(-profile.start_jitter_minutes, profile.start_jitter_minutes),
        step,
    )
    start = max(0, min(start, MINUTES_PER_DAY - step))

    duration = _snap(
        profile.duration_minutes_center
        + rng.randint(-profile.duration_jitter_minutes, profile.duration_jitter_minutes),
        step,
    )
    duration = max(min_duration, min(duration, MAX_SHIFT_MINUTES))

    return start, duration


def generate_type_a(
    seed: int,
    year: int,
    month: int,
    holidays: Mapping[date, str] | None = None,
    profile: GenerationProfile | None = None,
    rules: PayRules = DEFAULT_RULES,
) -> Generated:
    """Generate a Type A report (a staffing company; worked days only)."""
    holidays = holidays or {}
    rng = random.Random(seed)
    profile = profile or sample_profile(rng, ReportType.TYPE_A)

    employee = _make_employee(rng)
    company = rng.choice(_COMPANIES)
    workplace = rng.choice(_WORKPLACES)
    step = profile.granularity_minutes

    working = _decide_working_dates(
        rng, profile, _month_dates(year, month), holidays, holiday_blocks_work=False
    )

    days = []

    for current in working:
        start, gross = _draw_shift(rng, profile, min_duration=profile.break_minutes + step)

        if rng.random() < profile.overtime_probability:
            # A long day: net time = a regular day + extra, so that the 125%
            # (and possibly 150%) columns are really used.
            low, high = profile.overtime_extra_range_minutes
            extra = _snap(rng.randint(low, high), step)
            gross = min(
                rules.regular_day_minutes + extra + profile.break_minutes,
                MAX_SHIFT_MINUTES,
            )

        days.append(
            TypeADay(current, workplace, WorkShift(start, start + gross), profile.break_minutes)
        )

    report = SyntheticReportA(
        metadata=ReportMetadata(ReportType.TYPE_A, year, month, seed, __version__),
        employee=employee,
        company_name=company,
        days=tuple(days),
    )
    return Generated(profile, report)


def generate_type_b(
    seed: int,
    year: int,
    month: int,
    holidays: Mapping[date, str] | None = None,
    profile: GenerationProfile | None = None,
) -> Generated:
    """Generate a Type B report (monthly card; every calendar day is listed)."""
    holidays = holidays or {}
    rng = random.Random(seed)
    profile = profile or sample_profile(rng, ReportType.TYPE_B)

    if profile.hourly_rate_agorot is None:
        raise ValueError("A Type B profile needs hourly_rate_agorot.")

    employee = _make_employee(rng)
    dates = _month_dates(year, month)
    working = set(
        _decide_working_dates(rng, profile, dates, holidays, holiday_blocks_work=True)
    )

    days = []

    for current in dates:
        if current in working:
            start, duration = _draw_shift(rng, profile, min_duration=profile.granularity_minutes)
            days.append(TypeBDay(current, WorkShift(start, start + duration)))
        else:
            # Off days stay empty; a holiday is named in the notes column.
            days.append(TypeBDay(current, None, holidays.get(current, "")))

    report = SyntheticReportB(
        metadata=ReportMetadata(ReportType.TYPE_B, year, month, seed, __version__),
        employee=employee,
        hourly_rate_agorot=profile.hourly_rate_agorot,
        days=tuple(days),
    )
    return Generated(profile, report)
