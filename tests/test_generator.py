import re
from datetime import date

import pytest

from attendance_generator.generation_profile import GenerationProfile, sample_profile
from attendance_generator.generator import generate_type_a, generate_type_b
from attendance_generator.models import ReportType
from attendance_generator.pay_rules import DayKind, classify_day, split_type_a_day, total_rate_split
from attendance_generator.synthetic_models import (
    ReportMetadata,
    SyntheticEmployee,
    SyntheticReportA,
    SyntheticReportB,
    TypeADay,
    TypeBDay,
    WorkShift,
    summarize_b,
)
from attendance_generator.synthetic_validation import (
    SyntheticLimits,
    has_errors,
    validate_type_a,
    validate_type_b,
)

ALL_DAYS = (1.0,) * 7  # Monday .. Sunday, including Friday and Saturday
NO_SATURDAY = (1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0)


def make_profile(**overrides) -> GenerationProfile:
    values = dict(
        weekday_work_probability=ALL_DAYS,
        start_minute_center=8 * 60,
        start_jitter_minutes=0,
        duration_minutes_center=510,  # 8.5 hours gross, 8 net with the break
        duration_jitter_minutes=0,
        granularity_minutes=15,
        break_minutes=30,
        overtime_probability=0.0,
    )
    values.update(overrides)
    return GenerationProfile(**values)


def b_profile(**overrides) -> GenerationProfile:
    values = dict(
        weekday_work_probability=NO_SATURDAY,
        granularity_minutes=1,
        break_minutes=0,
        duration_minutes_center=180,
        hourly_rate_agorot=3000,
    )
    values.update(overrides)
    return make_profile(**values)


# ------------------------------ profile ------------------------------------ #
@pytest.mark.parametrize(
    "overrides",
    [
        {"weekday_work_probability": (1.0,) * 6},
        {"weekday_work_probability": (1.5,) + (1.0,) * 6},
        {"granularity_minutes": 0},
        {"overtime_extra_range_minutes": (60, 30)},
        {"hourly_rate_agorot": 0},
        {"start_minute_center": 1440},
    ],
)
def test_profile_rejects_invalid_values(overrides):
    with pytest.raises(ValueError):
        make_profile(**overrides)


def test_sampled_profiles_are_reproducible_and_varied():
    import random

    first = sample_profile(random.Random(5), ReportType.TYPE_A)
    again = sample_profile(random.Random(5), ReportType.TYPE_A)
    assert first == again

    profiles = [sample_profile(random.Random(s), ReportType.TYPE_A) for s in range(60)]
    assert len({p.overtime_probability for p in profiles}) > 10
    assert all(p.granularity_minutes == 15 and p.hourly_rate_agorot is None for p in profiles)


def test_sampled_type_b_profile_has_a_valid_rate():
    import random

    for seed in range(50):
        profile = sample_profile(random.Random(seed), ReportType.TYPE_B)
        assert 2900 <= profile.hourly_rate_agorot <= 4000
        assert profile.hourly_rate_agorot % 5 == 0
        assert profile.weekday_work_probability[5] == 0.0  # never Saturday


def test_profile_can_only_be_drawn_for_a_known_type():
    import random

    with pytest.raises(ValueError):
        sample_profile(random.Random(1), ReportType.UNKNOWN)


# ----------------------------- determinism --------------------------------- #
def test_same_seed_gives_identical_reports():
    assert generate_type_a(7, 2023, 2) == generate_type_a(7, 2023, 2)
    assert generate_type_b(7, 2023, 2) == generate_type_b(7, 2023, 2)


def test_different_seeds_give_different_reports():
    assert generate_type_a(1, 2023, 2) != generate_type_a(2, 2023, 2)
    assert generate_type_b(1, 2023, 2) != generate_type_b(2, 2023, 2)


def test_metadata_and_employee_are_synthetic():
    generated = generate_type_b(42, 2023, 1)
    report = generated.report

    assert report.metadata.seed == 42
    assert report.metadata.is_synthetic
    assert report.employee.name.strip()
    assert re.fullmatch(r"S-\d{5}", report.employee.employee_id)


# --------------------- plausibility across many seeds ---------------------- #
def test_every_generated_report_is_valid():
    for seed in range(60):
        for month in range(1, 13):
            a = generate_type_a(seed, 2023, month).report
            b = generate_type_b(seed, 2023, month).report

            assert not has_errors(validate_type_a(a)), (seed, month)
            assert not has_errors(validate_type_b(b)), (seed, month)
            assert len(b.days) == b.metadata.days_in_month


def test_type_a_times_are_whole_quarter_hours():
    for seed in range(80):
        for day in generate_type_a(seed, 2023, 2).report.days:
            assert day.shift.start_minute % 15 == 0
            assert day.shift.end_minute % 15 == 0
            assert day.net_minutes % 15 == 0


def test_type_b_never_works_on_saturday_with_a_sampled_profile():
    for seed in range(50):
        report = generate_type_b(seed, 2023, 1).report
        assert all(not d.is_work_day for d in report.days if d.work_date.weekday() == 5)


def test_the_corpus_contains_no_overtime_some_overtime_and_150_percent():
    totals = [
        total_rate_split(generate_type_a(seed, 2023, 2).report)
        for seed in range(200)
    ]

    assert any(t.minutes_125 > 0 for t in totals)
    assert any(t.minutes_150 > 0 for t in totals)
    assert any(t.minutes_125 == 0 and t.minutes_150 == 0 for t in totals)


# ------------------------------ overtime ----------------------------------- #
def test_forced_long_days_use_the_125_and_150_columns():
    profile = make_profile(overtime_probability=1.0)
    report = generate_type_a(1, 2023, 2, profile=profile).report

    for day in report.days:
        if classify_day(day.work_date) is DayKind.REGULAR:
            assert 480 < day.net_minutes <= 720
            assert split_type_a_day(day).minutes_125 > 0


def test_no_overtime_profile_keeps_the_125_and_150_columns_empty():
    profile = make_profile(duration_minutes_center=450)  # 7 gross, 6.5 net
    total = total_rate_split(generate_type_a(1, 2023, 2, profile=profile).report)

    assert total.minutes_125 == 0
    assert total.minutes_150 == 0
    assert total.minutes_saturday > 0  # the profile works every Saturday
    assert total.minutes_100 > 0


# ------------------------------- holidays ---------------------------------- #
HOLIDAY = date(2023, 2, 1)  # a Wednesday


def test_type_a_holiday_work_follows_the_profile():
    works = generate_type_a(
        1, 2023, 2, {HOLIDAY: "חג"}, make_profile(holiday_work_probability=1.0)
    ).report
    skips = generate_type_a(
        1, 2023, 2, {HOLIDAY: "חג"}, make_profile(holiday_work_probability=0.0)
    ).report

    assert HOLIDAY in [d.work_date for d in works.days]
    assert HOLIDAY not in [d.work_date for d in skips.days]

    day = next(d for d in works.days if d.work_date == HOLIDAY)
    assert split_type_a_day(day, {HOLIDAY}).minutes_150 == day.net_minutes


def test_type_b_holiday_is_an_empty_named_day():
    report = generate_type_b(1, 2023, 2, {HOLIDAY: "חג"}, b_profile()).report
    day = next(d for d in report.days if d.work_date == HOLIDAY)

    assert not day.is_work_day
    assert day.note == "חג"


# ---------------------------- night shifts --------------------------------- #
def test_type_a_night_shifts_cross_midnight_and_are_valid():
    profile = make_profile(start_minute_center=22 * 60)
    report = generate_type_a(1, 2023, 2, profile=profile).report

    assert all(day.shift.crosses_midnight for day in report.days)
    assert not has_errors(validate_type_a(report))


def test_type_b_night_shifts_are_supported():
    profile = b_profile(start_minute_center=22 * 60, duration_minutes_center=480)
    report = generate_type_b(1, 2023, 2, profile=profile).report

    worked = [d for d in report.days if d.is_work_day]
    assert worked and all(d.shift.crosses_midnight and d.minutes == 480 for d in worked)


# ------------------------------- edge cases -------------------------------- #
def test_a_report_always_has_at_least_one_work_day():
    never = make_profile(weekday_work_probability=(0.0,) * 7)

    assert len(generate_type_a(1, 2023, 2, profile=never).report.days) == 1
    assert summarize_b(generate_type_b(1, 2023, 2, profile=b_profile(weekday_work_probability=(0.0,) * 7)).report).work_days == 1


def test_type_b_needs_an_hourly_rate():
    with pytest.raises(ValueError):
        generate_type_b(1, 2023, 2, profile=make_profile())


# ------------------------------ validation --------------------------------- #
def _meta(report_type):
    return ReportMetadata(report_type, 2023, 2, 1, "0.1.0")


EMPLOYEE = SyntheticEmployee("Test Person", "S-00001")


def test_validation_flags_a_day_that_is_too_long():
    long_day = TypeADay(date(2023, 2, 1), "Site", WorkShift(480, 480 + 13 * 60 + 30), 30)
    report = SyntheticReportA(_meta(ReportType.TYPE_A), EMPLOYEE, "Company", (long_day,))

    issues = validate_type_a(report)

    assert has_errors(issues)
    assert [i.code for i in issues] == ["DAILY_TOO_LONG"]


def test_validation_flags_empty_reports_and_monthly_excess():
    empty_a = SyntheticReportA(_meta(ReportType.TYPE_A), EMPLOYEE, "Company", ())
    assert [i.code for i in validate_type_a(empty_a)] == ["NO_WORK_DAYS"]

    days = tuple(TypeBDay(date(2023, 2, d)) for d in range(1, 29))
    empty_b = SyntheticReportB(_meta(ReportType.TYPE_B), EMPLOYEE, 3000, days)
    assert [i.code for i in validate_type_b(empty_b)] == ["NO_WORK_DAYS"]

    report = generate_type_a(1, 2023, 2, profile=make_profile()).report
    issues = validate_type_a(report, limits=SyntheticLimits(max_monthly_minutes=100))
    assert "MONTHLY_TOO_LONG" in [i.code for i in issues]
