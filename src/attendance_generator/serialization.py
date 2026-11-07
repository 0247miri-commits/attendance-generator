"""JSON export of a generated report.

The file is the "answer key" next to the PDF: canonical values (minutes,
agorot, ISO dates) plus the exact strings printed in the PDF. It always says
that the data is synthetic and carries the seed needed to reproduce it.

Money is exported as integer agorot and hours as strings, never as floats.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from .display import print_type_a, print_type_b
from .generator import Generated
from .models import ReportType
from .pay_rules import DEFAULT_RULES, PayRules, split_type_a_day
from .synthetic_models import (
    SyntheticReportA,
    SyntheticReportB,
    summarize_a,
    summarize_b,
)
from .units import format_clock

SCHEMA_VERSION = "1.0"
_WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _clock(minutes: int | None) -> str | None:
    return None if minutes is None else format_clock(minutes)


def _type_a_data(
    report: SyntheticReportA, holidays: Collection[date], rules: PayRules
) -> dict[str, Any]:
    summary = summarize_a(report)
    days = []

    for day in report.days:
        split = split_type_a_day(day, holidays, rules)
        days.append(
            {
                "date": day.work_date.isoformat(),
                "weekday": _WEEKDAY_KEYS[day.work_date.weekday()],
                "workplace": day.workplace,
                "start_minute": day.shift.start_minute,
                "end_minute": day.shift.end_minute,
                "start": _clock(day.shift.start_minute),
                "end": _clock(day.shift.end_minute),
                "crosses_midnight": day.shift.crosses_midnight,
                "break_minutes": day.break_minutes,
                "net_minutes": day.net_minutes,
                "rate_minutes": {
                    "100": split.minutes_100,
                    "125": split.minutes_125,
                    "150": split.minutes_150,
                    "saturday": split.minutes_saturday,
                },
            }
        )

    return {
        "company_name": report.company_name,
        "days": days,
        "summary": asdict(summary),
    }


def _type_b_data(report: SyntheticReportB) -> dict[str, Any]:
    summary = summarize_b(report)
    days = []

    for day in report.days:
        shift = day.shift
        days.append(
            {
                "date": day.work_date.isoformat(),
                "weekday": _WEEKDAY_KEYS[day.work_date.weekday()],
                "is_work_day": day.is_work_day,
                "start_minute": shift.start_minute if shift else None,
                "end_minute": shift.end_minute if shift else None,
                "start": _clock(shift.start_minute) if shift else None,
                "end": _clock(shift.end_minute) if shift else None,
                "crosses_midnight": shift.crosses_midnight if shift else False,
                "minutes": day.minutes,
                "note": day.note,
            }
        )

    summary_data = asdict(summary)
    summary_data["total_hours"] = f"{summary.total_hours:.2f}"  # Decimal -> string

    return {
        "hourly_rate_agorot": report.hourly_rate_agorot,
        "days": days,
        "summary": summary_data,
    }


def generated_to_dict(
    generated: Generated,
    holidays: Mapping[date, str] | None = None,
    rules: PayRules = DEFAULT_RULES,
) -> dict[str, Any]:
    """Convert a generated report to a JSON-ready dictionary."""
    holidays = holidays or {}
    report = generated.report
    meta = report.metadata
    month_holidays = {
        d.isoformat(): name for d, name in holidays.items()
        if (d.year, d.month) == (meta.year, meta.month)
    }

    if meta.report_type is ReportType.TYPE_A:
        data = _type_a_data(report, holidays.keys(), rules)
        printed = asdict(print_type_a(report, holidays.keys(), rules))
    else:
        data = _type_b_data(report)
        printed = asdict(print_type_b(report))

    profile = asdict(generated.profile)
    profile["weekday_work_probability"] = list(profile["weekday_work_probability"])
    profile["overtime_extra_range_minutes"] = list(profile["overtime_extra_range_minutes"])

    return {
        "schema_version": SCHEMA_VERSION,
        "is_synthetic": meta.is_synthetic,
        "generator_version": meta.generator_version,
        "seed": meta.seed,
        "report_type": meta.report_type.value,
        "period": {"year": meta.year, "month": meta.month},
        "employee": asdict(report.employee),
        "calendar": {"holidays": month_holidays},
        "profile": profile,
        "data": data,
        "printed": printed,
    }


def write_json(data: dict[str, Any], path: Path) -> None:
    """Write UTF-8 JSON, keeping Hebrew readable (no \\u escapes)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
