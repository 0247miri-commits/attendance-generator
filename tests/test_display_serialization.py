import json
from datetime import date

from attendance_generator.display import print_type_a, print_type_b
from attendance_generator.generator import generate_type_a, generate_type_b
from attendance_generator.serialization import generated_to_dict, write_json

from test_pay_rules import october_report
from test_synthetic_models import january_report

OCT_HOLIDAYS = {date(2022, 10, 17)}


# ------------------- Type B: January 2023 sample --------------------------- #
def test_type_b_header_matches_the_sample():
    printed = print_type_b(january_report())

    assert printed.work_days == "21"
    assert printed.total_hours == "63.02"
    assert printed.hourly_rate == "32.35"
    assert printed.total_pay == "2,038.59"
    assert printed.month_label == "ינו-23"


def test_type_b_rows_match_the_sample():
    rows = print_type_b(january_report()).rows

    assert len(rows) == 31
    assert (rows[0].date, rows[0].weekday, rows[0].start, rows[0].end, rows[0].hours) == (
        "1/1/23", "ראשון", "8:01", "11:05", "3.07",
    )
    assert rows[2].hours == "2.88"  # 3/1: 8:04 - 10:57
    assert rows[4].start == rows[4].hours == ""  # 5/1 (Thursday) is empty
    assert rows[6].weekday == "שבת" and rows[6].is_saturday
    assert rows[30].hours == "3.17"  # 31/1


# ------------------- Type A: October 2022 sample --------------------------- #
def test_type_a_rows_match_the_sample():
    rows = print_type_a(october_report(), OCT_HOLIDAYS).rows
    by_date = {row.date: row for row in rows}

    first = rows[0]
    assert (first.date, first.weekday, first.start, first.end, first.break_time) == (
        "02/10/2022", "יום ראשון", "08:00", "15:00", "00:30",
    )
    assert (first.total, first.hours_100, first.hours_125, first.hours_150, first.saturday) == (
        "6.50", "6.50", "0.00", "0.00", "0.00",
    )

    saturday = by_date["08/10/2022"]
    assert saturday.weekday == "שבת" and saturday.is_saturday
    assert (saturday.hours_100, saturday.saturday) == ("0.00", "6.50")

    holiday = by_date["17/10/2022"]
    assert (holiday.hours_100, holiday.hours_150) == ("0.00", "6.50")


def test_type_a_totals_and_summary_box_match_the_sample():
    printed = print_type_a(october_report(), OCT_HOLIDAYS)
    totals, box = printed.totals, printed.summary_box

    assert (totals.days, totals.break_total, totals.total) == ("22", "11:00", "143.00")
    assert (totals.hours_100, totals.hours_125, totals.hours_150, totals.saturday) == (
        "117.00", "0.00", "6.50", "19.50",
    )
    assert (box.days, box.total_hours, box.hours_100, box.hours_125) == ("22", "143", "117", "0")
    assert (box.hours_150, box.saturday, box.bonus, box.travel) == ("6.5", "19.5", "0", "0")


# ------------------------------- JSON -------------------------------------- #
def test_json_marks_the_data_as_synthetic_and_reproducible():
    data = generated_to_dict(generate_type_b(11, 2023, 1))

    assert data["is_synthetic"] is True
    assert data["seed"] == 11
    assert data["report_type"] == "type_b"
    assert data["period"] == {"year": 2023, "month": 1}
    assert data["schema_version"] == "1.0"
    assert data["printed"]["month_label"] == "ינו-23"


def test_json_is_serialisable_and_deterministic():
    first = generated_to_dict(generate_type_a(5, 2023, 2))
    second = generated_to_dict(generate_type_a(5, 2023, 2))

    assert json.dumps(first, ensure_ascii=False) == json.dumps(second, ensure_ascii=False)


def test_json_type_a_pay_columns_add_up_to_net_minutes():
    holidays = {date(2023, 2, 1): "חג"}
    data = generated_to_dict(generate_type_a(9, 2023, 2, holidays), holidays)

    for day in data["data"]["days"]:
        assert sum(day["rate_minutes"].values()) == day["net_minutes"]

    assert data["calendar"]["holidays"] == {"2023-02-01": "חג"}


def test_json_type_b_summary_matches_the_rows():
    data = generated_to_dict(generate_type_b(3, 2023, 2))["data"]
    worked = [d for d in data["days"] if d["is_work_day"]]

    assert data["summary"]["work_days"] == len(worked)
    assert data["summary"]["total_minutes"] == sum(d["minutes"] for d in worked)
    assert isinstance(data["summary"]["total_hours"], str)  # never a float
    assert len(data["days"]) == 28


def test_json_keeps_hebrew_readable_on_disk(tmp_path):
    path = tmp_path / "sub" / "report.json"
    write_json(generated_to_dict(generate_type_b(3, 2023, 1)), path)

    text = path.read_text(encoding="utf-8")
    assert "ראשון" in text
    assert "\\u05" not in text
    assert json.loads(text)["is_synthetic"] is True
