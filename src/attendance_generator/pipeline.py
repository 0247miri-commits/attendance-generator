"""High-level orchestration; concrete OCR and parsers will be connected later."""
from .models import ExtractedReport, QualityAssessment
from .quality import assess_extraction


def assess_source_report(
    report: ExtractedReport,
    *,
    required_fields: tuple[str, ...],
) -> QualityAssessment:
    return assess_extraction(report, required_fields=required_fields)
