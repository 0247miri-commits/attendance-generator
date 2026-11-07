"""Validation of SYNTHETIC reports (ADR-007, second validation system).

This is separate from ``quality.py``, which judges whether data EXTRACTED from
a source document can be trusted. Here the data was produced by us, so a
failure is a bug in generation: the report should be regenerated or repaired,
not sent to a human.

Structural rules (valid month, ascending dates, break shorter than shift) are
already enforced when the objects are created. This module adds the plausibility
and consistency checks that need several days at once.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

from .models import Severity, ValidationIssue
from .pay_rules import DEFAULT_RULES, PayRules, total_rate_split
from .synthetic_models import (
    SyntheticReportA,
    SyntheticReportB,
    summarize_a,
    summarize_b,
)


@dataclass(frozen=True)
class SyntheticLimits:
    """Plausibility limits. Assumptions, not taken from the sample reports."""

    max_daily_net_minutes: int = 12 * 60
    max_monthly_minutes: int = 260 * 60


DEFAULT_LIMITS = SyntheticLimits()


def _error(code: str, message: str, field_name: str | None = None) -> ValidationIssue:
    return ValidationIssue(code, message, Severity.ERROR, field_name)


def validate_type_a(
    report: SyntheticReportA,
    holidays: Collection[date] = (),
    rules: PayRules = DEFAULT_RULES,
    limits: SyntheticLimits = DEFAULT_LIMITS,
) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []

    if not report.days:
        issues.append(_error("NO_WORK_DAYS", "The report has no work days."))

    for day in report.days:
        if day.net_minutes > limits.max_daily_net_minutes:
            issues.append(
                _error("DAILY_TOO_LONG", f"{day.work_date}: net time is above the daily limit.", "days")
            )

    summary = summarize_a(report)

    if summary.total_net_minutes > limits.max_monthly_minutes:
        issues.append(_error("MONTHLY_TOO_LONG", "Monthly hours are above the limit.", "summary"))

    # The pay columns must always add up to the worked time.
    if total_rate_split(report, holidays, rules).total_minutes != summary.total_net_minutes:
        issues.append(_error("SPLIT_MISMATCH", "Pay columns do not add up to worked time.", "summary"))

    return tuple(issues)


def validate_type_b(
    report: SyntheticReportB,
    limits: SyntheticLimits = DEFAULT_LIMITS,
) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    summary = summarize_b(report)

    if summary.work_days == 0:
        issues.append(_error("NO_WORK_DAYS", "The report has no work days."))

    for day in report.days:
        if day.minutes > limits.max_daily_net_minutes:
            issues.append(
                _error("DAILY_TOO_LONG", f"{day.work_date}: shift is above the daily limit.", "days")
            )

    if summary.total_minutes > limits.max_monthly_minutes:
        issues.append(_error("MONTHLY_TOO_LONG", "Monthly hours are above the limit.", "summary"))

    return tuple(issues)


def has_errors(issues: Collection[ValidationIssue]) -> bool:
    return any(issue.severity is Severity.ERROR for issue in issues)
