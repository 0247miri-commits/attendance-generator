import pytest
from attendance_generator.models import ExtractedField, ExtractedReport, ReportType


def test_invalid_confidence_is_rejected():
    with pytest.raises(ValueError):
        ExtractedField("entry_time", "08:00", 1.5)


def test_report_stores_extracted_fields():
    report = ExtractedReport("sample.pdf", ReportType.TYPE_A)
    report.add_field(ExtractedField("employee_code", "SYN-001", 0.99))
    assert report.fields["employee_code"].value == "SYN-001"

def test_raw_value_is_preserved():
    field = ExtractedField(
        name="total_hours",
        value="3.07",
        confidence=0.99,
        raw_value="3.07",
        source_text="3.07",
    )

    assert field.value == "3.07"
    assert field.raw_value == "3.07"


def test_confidence_nan_is_rejected():
    with pytest.raises(ValueError):
        ExtractedField("entry_time", "08:00", float("nan"))


def test_confidence_infinity_is_rejected():
    with pytest.raises(ValueError):
        ExtractedField("entry_time", "08:00", float("inf"))


def test_invalid_report_period_is_rejected():
    from datetime import date

    with pytest.raises(ValueError):
        ExtractedReport(
            "sample.pdf",
            ReportType.TYPE_A,
            detected_period_start=date(2026, 2, 1),
            detected_period_end=date(2026, 1, 1),
        )
