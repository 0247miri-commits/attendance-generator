
from datetime import date
from decimal import Decimal

import pytest

from attendance_generator.report_b import (
    TypeBDailyRow,
    TypeBReport,
)
from attendance_generator.work_profile import (
    DistributionProfile,
    build_type_b_profile,
    parse_time_to_minutes,
)


def test_parse_time_to_minutes():
    assert parse_time_to_minutes("08:00") == 480
    assert parse_time_to_minutes("12:30") == 750


def test_invalid_time_is_rejected():
    with pytest.raises(ValueError):
        parse_time_to_minutes("25:90")


def test_distribution_statistics():
    profile = DistributionProfile(
        values=(
            Decimal("2"),
            Decimal("4"),
            Decimal("6"),
        )
    )

    assert profile.count == 3
    assert profile.minimum == Decimal("2")
    assert profile.maximum == Decimal("6")
    assert profile.average == Decimal("4")
    assert profile.median == Decimal("4")


def test_empty_distribution():
    profile = DistributionProfile(values=())

    assert profile.count == 0
    assert profile.average is None
    assert profile.median is None


def test_build_type_b_profile():
    report = TypeBReport(
        source_file="sample.pdf",
        rows=(
            TypeBDailyRow(
                work_date=date(2023, 1, 1),
                entry_time="08:00",
                total_hours=Decimal("7.50"),
            ),
            TypeBDailyRow(
                work_date=date(2023, 1, 2),
                entry_time="08:15",
                total_hours=Decimal("8.00"),
            ),
            TypeBDailyRow(
                work_date=date(2023, 1, 3),
                entry_time="07:45",
                total_hours=Decimal("6.75"),
            ),
        ),
    )

    profile = build_type_b_profile(report)

    assert profile.observed_workdays == 3
    assert profile.daily_hours.count == 3
    assert profile.daily_hours.average == Decimal("7.416666666666666666666666667")
    assert profile.start_times_minutes.count == 3


def test_missing_values_are_not_counted_as_zero():
    report = TypeBReport(
        source_file="sample.pdf",
        rows=(
            TypeBDailyRow(
                work_date=date(2023, 1, 1),
                total_hours=None,
            ),
        ),
    )

    profile = build_type_b_profile(report)

    assert profile.observed_workdays == 0
    assert profile.daily_hours.count == 0
    assert profile.start_times_minutes.count == 0
