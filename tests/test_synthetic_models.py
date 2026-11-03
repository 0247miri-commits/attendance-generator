from datetime import date, timedelta
from decimal import Decimal

import pytest

from attendance_generator.models import ReportType
from attendance_generator.synthetic_models import (
    ReportMetadata,
    SyntheticEmployee,
    SyntheticReportA,
    SyntheticReportB,
    TypeADay,
    TypeBDay,
    WorkShift,
    summarize_a,
    summarize_b,
)
from attendance_generator.units import parse_clock

EMPLOYEE = SyntheticEmployee(name="Test Person", employee_id="S-0001")


def meta(report_type, year=2023, month=1):
    return ReportMetadata(report_type, year, month, seed=1, generator_version="0.1.0")


def shift(start: str, end: str) -> WorkShift:
    return WorkShift(parse_clock(start), parse_clock(end))


# ----------------------------- WorkShift ---------------------------------- #
def test_shift_duration():
    assert shift("8:01", "11:05").duration_minutes == 184


def test_shift_rejects_end_not_after_start():
    with pytest.raises(ValueError):
        WorkShift(600, 600)
    with pytest.raises(ValueError):
        WorkShift(600, 500)


def test_night_shift_is_supported():
    night = WorkShift(22 * 60, 30 * 60)  # 22:00 -> 06:00 next day
    assert night.duration_minutes == 8 * 60
    assert night.crosses_midnight


def test_shift_ending_exactly_at_midnight_does_not_cross():
    assert not WorkShift(16 * 60, 24 * 60).crosses_midnight


def test_shift_rejects_start_outside_day_and_too_long():
    with pytest.raises(ValueError):
        WorkShift(1440, 1500)
    with pytest.raises(ValueError):
        WorkShift(0, 17 * 60)


def test_shift_rejects_non_int():
    with pytest.raises(TypeError):
        WorkShift(480.0, 900)  # type: ignore[arg-type]


# --------------------------- Metadata / employee --------------------------- #
def test_metadata_validation():
    with pytest.raises(ValueError):
        ReportMetadata(ReportType.UNKNOWN, 2023, 1, 1, "0.1.0")
    with pytest.raises(ValueError):
        meta(ReportType.TYPE_A, month=13)


def test_metadata_is_always_synthetic_and_knows_month_length():
    assert meta(ReportType.TYPE_B).is_synthetic
    assert meta(ReportType.TYPE_B, month=2).days_in_month == 28
    assert meta(ReportType.TYPE_B, year=2024, month=2).days_in_month == 29


def test_employee_requires_name_and_id():
    with pytest.raises(ValueError):
        SyntheticEmployee(name=" ", employee_id="S-1")


# ------------------------------- Type A ------------------------------------ #
def a_day(day: int, start="08:00", end="16:00", brk=30) -> TypeADay:
    return TypeADay(date(2023, 2, day), "Site 1", shift(start, end), brk)


def test_type_a_day_net_minutes_matches_sample():
    assert a_day(1).net_minutes == 450  # 7.50 hours
    assert a_day(13, end="15:00").net_minutes == 390  # 6.50 hours


def test_type_a_break_must_be_shorter_than_shift():
    with pytest.raises(ValueError):
        a_day(1, start="08:00", end="08:30", brk=30)


def test_type_a_summary_matches_february_sample():
    days = tuple(a_day(d) for d in (1, 2, 5, 7, 12, 14, 15, 16, 19, 20, 22, 26, 27))
    days += (a_day(13, end="15:00"), a_day(23, end="15:00"))
    days = tuple(sorted(days, key=lambda day: day.work_date))
    report = SyntheticReportA(meta(ReportType.TYPE_A, month=2), EMPLOYEE, "Company", days)

    summary = summarize_a(report)

    assert summary.work_days == 15
    assert summary.total_net_minutes == 110.5 * 60
    assert summary.total_break_minutes == 7 * 60 + 30  # shown as 07:30


def test_type_a_report_rejects_wrong_month_order_and_type():
    with pytest.raises(ValueError):  # day outside the month
        SyntheticReportA(
            meta(ReportType.TYPE_A, month=3), EMPLOYEE, "Company", (a_day(1),)
        )
    with pytest.raises(ValueError):  # not ascending
        SyntheticReportA(
            meta(ReportType.TYPE_A, month=2), EMPLOYEE, "Company", (a_day(2), a_day(1))
        )
    with pytest.raises(ValueError):  # metadata says Type B
        SyntheticReportA(meta(ReportType.TYPE_B, month=2), EMPLOYEE, "Company", (a_day(1),))


# ------------------------------- Type B ------------------------------------ #
# Entry/exit times from the January 2023 sample (times only, no personal data).
JAN_2023 = {
    1: ("8:01", "11:05"), 2: ("8:03", "11:03"), 3: ("8:04", "10:57"), 4: ("8:01", "10:59"),
    8: ("8:02", "11:03"), 9: ("8:00", "10:57"), 10: ("8:03", "11:01"), 11: ("8:00", "11:02"),
    15: ("8:04", "11:01"), 16: ("8:02", "11:03"), 17: ("8:00", "11:01"), 18: ("8:01", "11:02"),
    19: ("8:06", "11:02"), 22: ("8:02", "11:03"), 23: ("8:10", "11:12"), 24: ("8:01", "11:04"),
    25: ("8:06", "11:03"), 26: ("8:02", "11:00"), 29: ("8:01", "11:03"), 30: ("8:02", "11:01"),
    31: ("8:00", "11:10"),
}


def january_report(**overrides) -> SyntheticReportB:
    days = tuple(
        TypeBDay(date(2023, 1, d), shift(*JAN_2023[d]) if d in JAN_2023 else None)
        for d in range(1, 32)
    )
    values = dict(
        metadata=meta(ReportType.TYPE_B),
        employee=EMPLOYEE,
        hourly_rate_agorot=3235,
        days=days,
    )
    values.update(overrides)
    return SyntheticReportB(**values)


def test_type_b_summary_reproduces_the_january_sample():
    summary = summarize_b(january_report())

    assert summary.work_days == 21
    assert summary.total_minutes == 3781
    assert summary.total_hours == Decimal("63.02")
    assert summary.total_pay_agorot == 203859  # 2,038.59


def test_type_b_day_off_has_no_minutes():
    day = TypeBDay(date(2023, 1, 5))
    assert not day.is_work_day
    assert day.minutes == 0


def test_type_b_requires_every_day_of_the_month():
    report = january_report()
    with pytest.raises(ValueError):
        january_report(days=report.days[:-1])


def test_type_b_rejects_gap_or_duplicate_dates():
    days = list(january_report().days)
    days[5] = TypeBDay(days[4].work_date)  # duplicate date, same length
    with pytest.raises(ValueError):
        january_report(days=tuple(days))


def test_type_b_rejects_list_instead_of_tuple_and_bad_rate():
    with pytest.raises(TypeError):
        january_report(days=list(january_report().days))
    with pytest.raises(ValueError):
        january_report(hourly_rate_agorot=0)


def test_summary_is_recalculated_not_stored():
    first = summarize_b(january_report())
    second = summarize_b(january_report(hourly_rate_agorot=3000))
    assert first.total_pay_agorot != second.total_pay_agorot
    assert first.total_minutes == second.total_minutes


def test_february_2024_has_29_days():
    start = date(2024, 2, 1)
    days = tuple(TypeBDay(start + timedelta(days=i)) for i in range(29))
    report = SyntheticReportB(
        meta(ReportType.TYPE_B, year=2024, month=2), EMPLOYEE, 3000, days
    )
    assert summarize_b(report).work_days == 0
