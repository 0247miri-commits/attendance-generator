from attendance_generator.models import (
    ExtractedField, ExtractedReport, ReportType, ReviewStatus, Severity,
    ValidationIssue,
)
from attendance_generator.quality import assess_extraction


def sample(confidence=0.99):
    report = ExtractedReport("sample.pdf", ReportType.TYPE_A)
    report.add_field(ExtractedField("employee_code", "SYN-001", confidence))
    report.add_field(ExtractedField("period", "2026-01", confidence))
    return report


def test_good_extraction_is_approved_automatically():
    result = assess_extraction(sample(), required_fields=("employee_code", "period"))
    assert result.status == ReviewStatus.APPROVED_AUTOMATICALLY


def test_missing_field_requires_review():
    result = assess_extraction(
        sample(), required_fields=("employee_code", "period", "daily_rows")
    )
    assert result.status == ReviewStatus.NEEDS_HUMAN_REVIEW
    assert result.missing_required_fields == ("daily_rows",)


def test_low_confidence_requires_review():
    result = assess_extraction(
        sample(0.60), required_fields=("employee_code", "period")
    )
    assert result.status == ReviewStatus.NEEDS_HUMAN_REVIEW


def test_error_blocks_current_extraction():
    report = sample()
    report.issues.append(ValidationIssue(
        "BAD_PERIOD", "Invalid period.", Severity.ERROR
    ))
    result = assess_extraction(report, required_fields=("employee_code", "period"))
    assert result.status == ReviewStatus.REJECTED
