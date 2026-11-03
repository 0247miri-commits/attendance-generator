from decimal import Decimal

import pytest

from attendance_generator.units import (
    decimal_hours_to_minutes,
    format_clock,
    format_money,
    minutes_to_decimal_hours,
    parse_clock,
    pay_agorot,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("8:05", 485), ("08:05", 485), ("00:00", 0), ("23:59", 1439), (" 11:05 ", 665)],
)
def test_parse_clock(text, expected):
    assert parse_clock(text) == expected


@pytest.mark.parametrize("text", ["", "8", "8:5x", "24:00", "12:60", "a:b", "-1:30", None])
def test_parse_clock_rejects_invalid(text):
    with pytest.raises(ValueError):
        parse_clock(text)


def test_format_clock_padding_and_midnight_wrap():
    assert format_clock(485) == "08:05"
    assert format_clock(485, zero_pad_hour=False) == "8:05"
    assert format_clock(1800) == "06:00"  # 22:00 shift ending after midnight


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(184, "3.07"), (180, "3.00"), (173, "2.88"), (210, "3.50"), (3781, "63.02")],
)
def test_minutes_to_decimal_hours_matches_sample_rows(minutes, expected):
    assert minutes_to_decimal_hours(minutes) == Decimal(expected)


def test_decimal_hours_to_minutes_is_lossy_but_stable():
    assert decimal_hours_to_minutes(Decimal("3.50")) == 210
    assert decimal_hours_to_minutes(Decimal("3.07")) == 184  # 184.2 -> 184


def test_decimal_hours_to_minutes_rejects_float():
    with pytest.raises(ValueError):
        decimal_hours_to_minutes(3.5)  # type: ignore[arg-type]


def test_pay_is_rounded_once_from_exact_minutes():
    # January 2023 sample: 3781 minutes at 32.35 -> 2,038.59 (not 2,038.70).
    assert pay_agorot(3781, 3235) == 203859
    assert format_money(203859) == "2,038.59"


def test_pay_sample_september():
    assert pay_agorot(84 * 60, 3065) == 257460


def test_pay_rejects_negative_and_bool():
    with pytest.raises(ValueError):
        pay_agorot(-1, 3235)
    with pytest.raises(ValueError):
        pay_agorot(True, 3235)  # type: ignore[arg-type]
