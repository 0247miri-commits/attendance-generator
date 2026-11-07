import dataclasses
from datetime import date

import pytest

from attendance_generator.generator import generate_type_a
from attendance_generator.render_type_a import render_type_a
from attendance_generator.synthetic_models import SyntheticEmployee

from test_pay_rules import october_report

pymupdf = pytest.importorskip("pymupdf")

HOLIDAYS = {date(2022, 10, 17)}


def october_with_name():
    return dataclasses.replace(october_report(), employee=SyntheticEmployee("דנה לוי", "S-00001"))


def test_renders_a_one_page_pdf(tmp_path):
    path = render_type_a(october_with_name(), tmp_path / "out" / "oct.pdf", HOLIDAYS)

    assert path.read_bytes().startswith(b"%PDF")
    assert pymupdf.open(path).page_count == 1


def test_printed_numbers_appear_on_the_page(tmp_path):
    path = render_type_a(october_with_name(), tmp_path / "oct.pdf", HOLIDAYS)
    text = pymupdf.open(path)[0].get_text()

    for expected in ("117.00", "143.00", "19.50", "11:00", "02/10/2022", "31/10/2022"):
        assert expected in text


def test_same_report_gives_identical_bytes(tmp_path):
    first = render_type_a(october_with_name(), tmp_path / "a.pdf", HOLIDAYS).read_bytes()
    second = render_type_a(october_with_name(), tmp_path / "b.pdf", HOLIDAYS).read_bytes()

    assert first == second


def test_metadata_says_the_document_is_synthetic(tmp_path):
    report = generate_type_a(42, 2023, 2).report
    metadata = pymupdf.open(render_type_a(report, tmp_path / "x.pdf")).metadata

    assert "SYNTHETIC" in metadata["subject"]
    assert "seed=42" in metadata["keywords"]


@pytest.mark.parametrize("seed", range(5))
def test_generated_reports_fit_one_page(tmp_path, seed):
    report = generate_type_a(seed, 2023, 1).report

    assert pymupdf.open(render_type_a(report, tmp_path / "g.pdf")).page_count == 1
