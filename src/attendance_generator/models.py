"""Generic models; report-specific fields will be added after source analysis."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class ReportType(str, Enum):
    TYPE_A = "type_a"
    TYPE_B = "type_b"
    UNKNOWN = "unknown"


class ReviewStatus(str, Enum):
    APPROVED_AUTOMATICALLY = "approved_automatically"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    REJECTED = "rejected"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ExtractedField:
    name: str
    value: Any
    confidence: float
    source_page: int | None = None
    source_text: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Field name cannot be empty.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0.")
        if self.source_page is not None and self.source_page < 1:
            raise ValueError("Page numbers start at 1.")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: Severity
    field_name: str | None = None


@dataclass
class ExtractedReport:
    source_file: str
    report_type: ReportType
    fields: dict[str, ExtractedField] = field(default_factory=dict)
    detected_period_start: date | None = None
    detected_period_end: date | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_field(self, extracted_field: ExtractedField) -> None:
        self.fields[extracted_field.name] = extracted_field


@dataclass(frozen=True)
class QualityAssessment:
    status: ReviewStatus
    average_confidence: float
    low_confidence_fields: tuple[str, ...]
    missing_required_fields: tuple[str, ...]
    issues: tuple[ValidationIssue, ...]
    reasons: tuple[str, ...]
