"""Quality checks and routing to optional human review."""
from collections.abc import Iterable
from .models import (
    ExtractedReport, QualityAssessment, ReviewStatus, Severity,
)

# Initial thresholds only; calibrate against real source documents.
MIN_FIELD_CONFIDENCE = 0.85
MIN_AVERAGE_CONFIDENCE = 0.92


def assess_extraction(
    report: ExtractedReport,
    *,
    required_fields: Iterable[str],
    min_field_confidence: float = MIN_FIELD_CONFIDENCE,
    min_average_confidence: float = MIN_AVERAGE_CONFIDENCE,
) -> QualityAssessment:
    """Assess extraction quality; this does not guarantee OCR correctness."""
    if not 0 <= min_field_confidence <= 1:
        raise ValueError("min_field_confidence must be between 0 and 1.")
    if not 0 <= min_average_confidence <= 1:
        raise ValueError("min_average_confidence must be between 0 and 1.")

    missing = tuple(name for name in required_fields if name not in report.fields)
    confidences = [item.confidence for item in report.fields.values()]
    average = sum(confidences) / len(confidences) if confidences else 0.0
    low = tuple(
        name for name, item in report.fields.items()
        if item.confidence < min_field_confidence
    )
    blocking = tuple(
        issue for issue in report.issues
        if issue.severity in (Severity.WARNING, Severity.ERROR)
    )

    reasons = []
    if report.report_type == report.report_type.UNKNOWN:
        reasons.append("Report type could not be identified.")
    if missing:
        reasons.append("Required fields are missing.")
    if low:
        reasons.append("One or more fields have low OCR confidence.")
    if average < min_average_confidence:
        reasons.append("Average OCR confidence is below the configured threshold.")
    if blocking:
        reasons.append("Validation produced warning or error issues.")

    if report.report_type == report.report_type.UNKNOWN or any(
        issue.severity == Severity.ERROR for issue in report.issues
    ):
        status = ReviewStatus.REJECTED
    elif reasons:
        status = ReviewStatus.NEEDS_HUMAN_REVIEW
    else:
        status = ReviewStatus.APPROVED_AUTOMATICALLY

    return QualityAssessment(
        status=status,
        average_confidence=average,
        low_confidence_fields=low,
        missing_required_fields=missing,
        issues=blocking,
        reasons=tuple(reasons),
    )
