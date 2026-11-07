import dataclasses

import pytest

from attendance_generator.generator import generate_type_b
from attendance_generator.render_type_b import render_type_b
from attendance_generator.synthetic_models import SyntheticEmployee

from test_synthetic_models import january_report

pymupdf = pytest.importorskip("pymupdf")


def jan_with_hebrew_name():
    return dataclasses.replace(january_report(), employee=SyntheticEmployee("דנה לוי", "S-00001"))


def test_renders_a_one_page_pdf(tmp_path):
    path = render_type_b(jan_with_hebrew_name(), tmp_path / "out" / "jan.pdf")

    assert path.read_bytes().startswith(b"%PDF")
    assert pymupdf.open(path).page_count == 1


def test_printed_numbers_appear_on_the_page(tmp_path):
    path = render_type_b(jan_with_hebrew_name(), tmp_path / "jan.pdf")
    text = pymupdf.open(path)[0].get_text()

    for expected in ("63.02", "32.35", "2,038.59", "1/1/23", "31/1/23", "11:10", "3.17"):
        assert expected in text


def test_same_report_gives_identical_bytes(tmp_path):
    first = render_type_b(jan_with_hebrew_name(), tmp_path / "a.pdf").read_bytes()
    second = render_type_b(jan_with_hebrew_name(), tmp_path / "b.pdf").read_bytes()

    assert first == second


def test_metadata_says_the_document_is_synthetic(tmp_path):
    generated = generate_type_b(42, 2023, 2)
    metadata = pymupdf.open(render_type_b(generated.report, tmp_path / "x.pdf")).metadata

    assert "SYNTHETIC" in metadata["subject"]
    assert "seed=42" in metadata["keywords"]


@pytest.mark.parametrize(("year", "month", "days"), [(2023, 2, 28), (2024, 2, 29), (2023, 4, 30), (2023, 1, 31)])
def test_every_month_length_renders(tmp_path, year, month, days):
    report = generate_type_b(1, year, month).report
    page = pymupdf.open(render_type_b(report, tmp_path / "m.pdf"))[0]

    assert len(report.days) == days
    assert page.get_text().count("/") >= days  # one printed date per day


def test_holiday_note_is_rendered(tmp_path):
    from datetime import date

    report = generate_type_b(1, 2023, 2, {date(2023, 2, 1): "חג"}).report
    path = render_type_b(report, tmp_path / "h.pdf")

    assert pymupdf.open(path).page_count == 1
