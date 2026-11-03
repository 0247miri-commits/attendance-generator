
from datetime import date

import pytest

from attendance_generator.report_a import (
    TypeADailyRow,
    TypeAReport,
    TypeASummary,
)


def test_daily_row_preserves_displayed_values():
    row = TypeADailyRow(
        work_date=date(2022, 10, 3),
        weekday="Monday",
        entry_time="08:00",
        exit_time="16:00",
        hours_125="1.50",
    )

    assert row.entry_time == "08:00"
    assert row.exit_time == "16:00"
    assert row.hours_125 == "1.50"


def test_optional_fields_can_be_empty():
    row = TypeADailyRow(
        work_date=date(2022, 10, 4),
    )

    assert row.entry_time is None
    assert row.workplace is None


def test_summary_preserves_bonus_and_travel():
    summary = TypeASummary(
        bonus_value="250.00",
        travel_value="100.00",
    )

    assert summary.bonus_value == "250.00"
    assert summary.travel_value == "100.00"


def test_complete_type_a_report():
    report = TypeAReport(
        source_file="sample_a.pdf",
        rows=(
            TypeADailyRow(
                work_date=date(2022, 10, 3),
                entry_time="08:00",
                exit_time="16:00",
            ),
        ),
    )

    assert report.source_file == "sample_a.pdf"
    assert len(report.rows) == 1


def test_empty_source_file_is_rejected():
    with pytest.raises(ValueError):
        TypeAReport(source_file=" ")


def test_multiple_daily_rows_are_preserved():
    report = TypeAReport(
        source_file="sample_a.pdf",
        rows=(
            TypeADailyRow(work_date=date(2022, 10, 3)),
            TypeADailyRow(work_date=date(2022, 10, 4)),
            TypeADailyRow(work_date=date(2022, 10, 5)),
        ),
    )

    assert len(report.rows) == 3