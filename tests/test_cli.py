import json

import pytest

from attendance_generator.cli import generate_corpus, main


def test_writes_pdf_json_and_manifest(tmp_path):
    manifest = generate_corpus(4, "mixed", seed=10, out=tmp_path)

    assert len(manifest["reports"]) == 4
    assert {r["type"] for r in manifest["reports"]} == {"A", "B"}

    for entry in manifest["reports"]:
        assert entry["valid"]
        assert (tmp_path / entry["pdf"]).read_bytes().startswith(b"%PDF")
        assert json.loads((tmp_path / entry["json"]).read_text(encoding="utf-8"))["seed"] == entry["seed"]

    assert (tmp_path / "manifest.json").exists()


def test_same_arguments_give_identical_files(tmp_path):
    first = generate_corpus(3, "mixed", seed=5, out=tmp_path / "a")
    second = generate_corpus(3, "mixed", seed=5, out=tmp_path / "b")

    assert first == second  # includes the sha256 of every file


def test_different_seed_gives_different_reports(tmp_path):
    a = generate_corpus(2, "A", seed=1, year=2023, month=3, out=tmp_path / "a")
    b = generate_corpus(2, "A", seed=100, year=2023, month=3, out=tmp_path / "b")

    assert a["reports"][0]["json_sha256"] != b["reports"][0]["json_sha256"]


def test_fixed_period_and_type(tmp_path):
    manifest = generate_corpus(3, "B", seed=0, year=2024, month=2, out=tmp_path)

    assert all(r["type"] == "B" and (r["year"], r["month"]) == (2024, 2) for r in manifest["reports"])


def test_main_returns_error_for_bad_input(tmp_path, capsys):
    assert main(["--count", "0", "--out", str(tmp_path)]) == 2
    assert main(["--month", "13", "--out", str(tmp_path)]) == 2
    assert "error" in capsys.readouterr().err


def test_main_success(tmp_path):
    assert main(["--count", "2", "--seed", "3", "--out", str(tmp_path), "--holiday", "2023-04-06=פסח"]) == 0


def test_bad_holiday_format_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        main(["--holiday", "06/04/2023", "--out", str(tmp_path)])
