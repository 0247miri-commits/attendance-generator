"""Command line: generate a corpus of synthetic attendance reports.

Example::

    python -m attendance_generator --count 20 --type mixed --seed 7 --out output

For every report the tool writes a PDF and a JSON "answer key", and at the end
a ``manifest.json`` listing all files. Report number ``i`` uses seed
``base_seed + i``, so any single report can be regenerated alone, and the whole
run is reproducible: the same arguments give the same bytes (no timestamps).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from . import __version__
from .generator import Generated, generate_type_a, generate_type_b
from .render_type_a import render_type_a
from .render_type_b import render_type_b
from .serialization import generated_to_dict, write_json
from .synthetic_validation import has_errors, validate_type_a, validate_type_b

YEAR_RANGE = (2022, 2024)  # used when --year is not given (assumption, adjustable)


def _parse_holiday(text: str) -> tuple[date, str]:
    """Parse ``YYYY-MM-DD`` or ``YYYY-MM-DD=name``."""
    day_text, _, name = text.partition("=")

    try:
        return date.fromisoformat(day_text), name or "חג"
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"bad holiday '{text}': use YYYY-MM-DD or YYYY-MM-DD=name") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="attendance_generator",
        description="Generate synthetic attendance report PDFs (+ JSON answer keys).",
    )
    parser.add_argument("--count", type=int, default=10, help="number of reports (default 10)")
    parser.add_argument("--type", choices=("A", "B", "mixed"), default="mixed", help="report type (default mixed)")
    parser.add_argument("--seed", type=int, default=0, help="base seed; report i uses seed+i (default 0)")
    parser.add_argument("--year", type=int, help="fixed year (default: drawn per report)")
    parser.add_argument("--month", type=int, help="fixed month 1-12 (default: drawn per report)")
    parser.add_argument("--holiday", action="append", default=[], type=_parse_holiday,
                        metavar="YYYY-MM-DD[=name]", help="a holiday date; may be repeated")
    parser.add_argument("--out", type=Path, default=Path("output"), help="output folder (default ./output)")
    return parser


def _pick_period(seed: int, year: int | None, month: int | None) -> tuple[int, int]:
    # A separate generator, so the report's own random stream is untouched.
    rng = random.Random(f"period-{seed}")
    return year or rng.randint(*YEAR_RANGE), month or rng.randint(1, 12)


def _pick_type(seed: int, choice: str) -> str:
    return choice if choice != "mixed" else ("A", "B")[seed % 2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_corpus(
    count: int,
    report_type: str = "mixed",
    seed: int = 0,
    year: int | None = None,
    month: int | None = None,
    holidays: dict[date, str] | None = None,
    out: Path = Path("output"),
) -> dict:
    """Write ``count`` reports into ``out`` and return the manifest."""
    if count < 1:
        raise ValueError("count must be at least 1")

    if month is not None and not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")

    holidays = holidays or {}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    entries = []

    for index in range(count):
        report_seed = seed + index
        kind = _pick_type(report_seed, report_type)
        y, m = _pick_period(report_seed, year, month)
        generated: Generated
        stem = f"report_{index + 1:04d}_{kind}_{y}-{m:02d}_seed{report_seed}"

        if kind == "A":
            generated = generate_type_a(report_seed, y, m, holidays)
            issues = validate_type_a(generated.report, holidays.keys())
        else:
            generated = generate_type_b(report_seed, y, m, holidays)
            issues = validate_type_b(generated.report)

        entry = {"id": stem, "type": kind, "seed": report_seed, "year": y, "month": m}

        if has_errors(issues):  # should not happen; never write an invalid report
            entry.update(valid=False, issues=[issue.code for issue in issues])
            entries.append(entry)
            continue

        pdf, js = out / f"{stem}.pdf", out / f"{stem}.json"

        if kind == "A":
            render_type_a(generated.report, pdf, holidays.keys())
        else:
            render_type_b(generated.report, pdf)

        write_json(generated_to_dict(generated, holidays), js)
        entry.update(valid=True, pdf=pdf.name, json=js.name, pdf_sha256=_sha256(pdf), json_sha256=_sha256(js))
        entries.append(entry)

    manifest = {
        "schema_version": "1.0",
        "is_synthetic": True,
        "generator_version": __version__,
        "arguments": {"count": count, "type": report_type, "seed": seed, "year": year, "month": month,
                      "holidays": {d.isoformat(): n for d, n in sorted(holidays.items())}},
        "reports": entries,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        manifest = generate_corpus(args.count, args.type, args.seed, args.year, args.month,
                                   dict(args.holiday), args.out)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    bad = [r for r in manifest["reports"] if not r["valid"]]
    print(f"Wrote {len(manifest['reports']) - len(bad)} reports to {args.out} (manifest.json)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
