
"""Generic data models for attendance report extraction and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from math import isfinite
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
    """
    A single field extracted from a source document.

    value: normalized or parsed value.
    raw_value: original value before normalization, when available.
    source_text: text as detected by OCR.
    confidence: extraction confidence between 0 and 1.
    """

    name: str
    value: Any
    confidence: float
    source_page: int | None = None
    source_text: str | None = None
    raw_value: Any | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Field name cannot be empty.")

        if not isfinite(self.confidence):
            raise ValueError("Confidence must be a finite number.")

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

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Issue code cannot be empty.")

        if not self.message.strip():
            raise ValueError("Issue message cannot be empty.")


@dataclass
class ExtractedReport:
    """Data extracted from one original attendance report."""

    source_file: str
    report_type: ReportType
    fields: dict[str, ExtractedField] = field(default_factory=dict)
    detected_period_start: date | None = None
    detected_period_end: date | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.source_file.strip():
            raise ValueError("Source file cannot be empty.")

        if (
            self.detected_period_start is not None
            and self.detected_period_end is not None
            and self.detected_period_start > self.detected_period_end
        ):
            raise ValueError("Report period start cannot be after its end.")

        for key, extracted_field in self.fields.items():
            if key != extracted_field.name:
                raise ValueError(
                    "Field dictionary keys must match field names."
                )

    def add_field(self, extracted_field: ExtractedField) -> None:
        """Add or replace an extracted field by its name."""
        self.fields[extracted_field.name] = extracted_field


@dataclass(frozen=True)
class QualityAssessment:
    """Result of checking the quality of source extraction."""

    status: ReviewStatus
    average_confidence: float
    low_confidence_fields: tuple[str, ...]
    missing_required_fields: tuple[str, ...]
    issues: tuple[ValidationIssue, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isfinite(self.average_confidence):
            raise ValueError("Average confidence must be finite.")

        if not 0.0 <= self.average_confidence <= 1.0:
            raise ValueError(
                "Average confidence must be between 0.0 and 1.0."
            )
