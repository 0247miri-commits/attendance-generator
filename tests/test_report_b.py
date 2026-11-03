
from datetime import date
from decimal import Decimal

import pytest

from attendance_generator.report_b import (
    TypeBDailyRow,
    TypeBReport,
    TypeBSummary,
)


def test_decimal_hours_are_preserved():
    row = TypeBDailyRow(
        work_date=date(2023, 1, 2),
        total_hours=Decimal("3.07"),
    )

    assert row.total_hours == Decimal("3.07")


def test_blank_day_can_have_no_hours():
    row = TypeBDailyRow(
        work_date=date(2023, 1, 3),
        total_hours=None,
    )

    assert row.total_hours is None


def test_float_is_not_accepted_for_decimal_hours():
    with pytest.raises(TypeError):
        TypeBDailyRow(
            work_date=date(2023, 1, 2),
            total_hours=3.07,
        )


def test_negative_hours_are_rejected():
    with pytest.raises(ValueError):
        TypeBDailyRow(
            work_date=date(2023, 1, 2),
            total_hours=Decimal("-2.5"),
        )


def test_report_summary_preserves_decimal_values():
    summary = TypeBSummary(
        reported_workdays=21,
        reported_total_hours=Decimal("63.02"),
        hourly_rate=Decimal("32.35"),
        reported_total_payment=Decimal("2038.59"),
    )

    assert summary.reported_total_hours == Decimal("63.02")
    assert summary.hourly_rate == Decimal("32.35")
    assert summary.reported_total_payment == Decimal("2038.59")


def test_complete_type_b_report():
    report = TypeBReport(
        source_file="sample.pdf",
        rows=(
            TypeBDailyRow(
                work_date=date(2023, 1, 2),
                entry_time="08:00",
                exit_time="11:04",
                total_hours=Decimal("3.07"),
            ),
        ),
    )

    assert len(report.rows) == 1
    assert report.rows[0].entry_time == "08:00"