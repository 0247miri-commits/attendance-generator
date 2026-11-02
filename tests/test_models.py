import pytest
from attendance_generator.models import ExtractedField, ExtractedReport, ReportType


def test_invalid_confidence_is_rejected():
    with pytest.raises(ValueError):
        ExtractedField("entry_time", "08:00", 1.5)


def test_report_stores_extracted_fields():
    report = ExtractedReport("sample.pdf", ReportType.TYPE_A)
    report.add_field(ExtractedField("employee_code", "SYN-001", 0.99))
    assert report.fields["employee_code"].value == "SYN-001"
