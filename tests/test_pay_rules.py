from datetime import date

import pytest

from attendance_generator.models import ReportType
from attendance_generator.pay_rules import (
    DayKind,
    PayRules,
    RateSplit,
    classify_day,
    split_minutes,
    split_type_a_day,
    total_rate_split,
)
from attendance_generator.synthetic_models import (
    ReportMetadata,
    SyntheticEmployee,
    SyntheticReportA,
    TypeADay,
    WorkShift,
)

HOUR = 60


# ---------------------------- classify_day -------------------------------- #
def test_saturday_is_saturday():
    assert classify_day(date(2022, 10, 8)) is DayKind.SATURDAY


def test_friday_is_regular():
    assert classify_day(date(2022, 10, 7)) is DayKind.REGULAR


def test_listed_holiday_is_holiday():
    assert classify_day(date(2022, 10, 17), {date(2022, 10, 17)}) is DayKind.HOLIDAY


def test_saturday_wins_over_holiday():
    saturday = date(2022, 10, 8)
    assert classify_day(saturday, {saturday}) is DayKind.SATURDAY


# --------------------------- split_minutes -------------------------------- #
def test_short_day_is_all_100():
    assert split_minutes(390, DayKind.REGULAR) == RateSplit(minutes_100=390)


@pytest.mark.parametrize(
    ("net", "expected"),
    [
        (8 * HOUR, RateSplit(480, 0, 0)),  # exactly the threshold
        (8 * HOUR + 10, RateSplit(480, 10, 0)),
        (10 * HOUR, RateSplit(480, 120, 0)),  # exactly the 125% tier
        (11 * HOUR, RateSplit(480, 120, 60)),
        (0, RateSplit()),
    ],
)
def test_regular_day_thresholds(net, expected):
    assert split_minutes(net, DayKind.REGULAR) == expected


def test_saturday_stays_in_saturday_column_even_when_long():
    assert split_minutes(10 * HOUR, DayKind.SATURDAY) == RateSplit(minutes_saturday=600)


def test_holiday_is_all_150():
    assert split_minutes(390, DayKind.HOLIDAY) == RateSplit(minutes_150=390)


def test_custom_thresholds():
    rules = PayRules(regular_day_minutes=7 * HOUR, tier_125_minutes=HOUR)
    assert split_minutes(9 * HOUR, DayKind.REGULAR, rules) == RateSplit(420, 60, 60)


@pytest.mark.parametrize("kind", list(DayKind))
def test_split_always_adds_up_to_the_input(kind):
    for net in range(0, 16 * HOUR + 1, 7):
        assert split_minutes(net, kind).total_minutes == net


def test_rules_and_inputs_are_validated():
    with pytest.raises(ValueError):
        PayRules(regular_day_minutes=0)
    with pytest.raises(ValueError):
        split_minutes(-1, DayKind.REGULAR)
    with pytest.raises(ValueError):
        RateSplit(minutes_100=-5)


# ------------------------ October 2022 sample ------------------------------ #
OCT_DATES = [2, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23,
             25, 26, 27, 28, 30, 31]


def october_report() -> SyntheticReportA:
    days = tuple(
        TypeADay(date(2022, 10, d), "Site", WorkShift(8 * HOUR, 15 * HOUR), 30)
        for d in OCT_DATES
    )
    return SyntheticReportA(
        ReportMetadata(ReportType.TYPE_A, 2022, 10, 1, "0.1.0"),
        SyntheticEmployee("Test Person", "S-0001"),
        "Company",
        days,
    )


def test_october_sample_summary_is_reproduced():
    total = total_rate_split(october_report(), holidays={date(2022, 10, 17)})

    assert total.minutes_100 == 117 * HOUR
    assert total.minutes_125 == 0
    assert total.minutes_150 == 390  # 6.5 hours on 17/10
    assert total.minutes_saturday == 19 * HOUR + 30  # 8, 15, 22 October
    assert total.total_minutes == 143 * HOUR


def test_single_day_helper_matches_sample_rows():
    report = october_report()
    holiday = {date(2022, 10, 17)}
    by_date = {day.work_date.day: day for day in report.days}

    assert split_type_a_day(by_date[8], holiday) == RateSplit(minutes_saturday=390)
    assert split_type_a_day(by_date[17], holiday) == RateSplit(minutes_150=390)
    assert split_type_a_day(by_date[18], holiday) == RateSplit(minutes_100=390)


def test_night_shift_is_classified_by_start_date():
    # Friday 22:00 -> Saturday 06:00, break 30: regular day, 7.5 net hours.
    night = TypeADay(date(2022, 10, 7), "Site", WorkShift(22 * HOUR, 30 * HOUR), 30)
    assert split_type_a_day(night) == RateSplit(minutes_100=450)
