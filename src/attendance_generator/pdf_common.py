"""Drawing helpers shared by the Type A and Type B PDF renderers.

ReportLab draws glyphs left to right and measures y from the bottom of the
page. This module hides both details: callers use "top-based" coordinates in
points (like a ruler placed on the printed page) and give Hebrew in logical
order; any string containing Hebrew is reordered with the Unicode bidi
algorithm before drawing.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

try:  # python-bidi >= 0.5 exposes get_display at the top level
    from bidi import get_display
except ImportError:  # pragma: no cover - older python-bidi
    from bidi.algorithm import get_display

from .paths import FONT_DIR
from .synthetic_models import ReportMetadata

PAGE_WIDTH, PAGE_HEIGHT = A4

REGULAR = "LiberationSans"
BOLD = "LiberationSans-Bold"
GRID_WIDTH = 0.8

_HEBREW = re.compile("[֐-׿]")


def register_fonts() -> None:
    """Register the bundled Liberation Sans fonts (safe to call repeatedly)."""
    registered = set(pdfmetrics.getRegisteredFontNames())

    for name, filename in ((REGULAR, "LiberationSans-Regular.ttf"), (BOLD, "LiberationSans-Bold.ttf")):
        if name in registered:
            continue

        path = FONT_DIR / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Font file not found: {path}. Copy the Liberation Sans fonts into the 'fonts' folder."
            )

        pdfmetrics.registerFont(TTFont(name, str(path)))


def visual(text: str) -> str:
    """Reorder text containing Hebrew into drawing (left-to-right) order."""
    return get_display(text) if _HEBREW.search(text) else text


def baseline_for(top: float, bottom: float, size: float) -> float:
    """Baseline that vertically centres text between two y positions."""
    return (top + bottom) / 2 + size * 0.34


def new_canvas(path: Path, *, kind: str, metadata: ReportMetadata) -> Canvas:
    """Create a deterministic canvas whose metadata marks the file as synthetic.

    ``invariant=1`` removes dates and random ids, so the same report always
    produces the same bytes.
    """
    register_fonts()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    canvas = Canvas(str(path), pagesize=A4, invariant=1)
    canvas.setTitle(f"Synthetic attendance report (Type {kind}) {metadata.year}-{metadata.month:02d}")
    canvas.setAuthor("attendance-generator")
    canvas.setCreator("attendance-generator")
    canvas.setSubject("SYNTHETIC DATA: generated for testing, not a real report")
    canvas.setKeywords(
        f"synthetic; type={kind}; seed={metadata.seed}; generator={metadata.generator_version}"
    )
    return canvas


class Page:
    """Small drawing helper that works in top-based coordinates (points)."""

    def __init__(self, canvas: Canvas) -> None:
        self.canvas = canvas

    def y(self, top: float) -> float:
        return PAGE_HEIGHT - top

    def line(self, x0: float, y0: float, x1: float, y1: float, width: float = GRID_WIDTH) -> None:
        self.canvas.setLineWidth(width)
        self.canvas.line(x0, self.y(y0), x1, self.y(y1))

    def fill(self, x0: float, top: float, x1: float, bottom: float, gray: float) -> None:
        self.canvas.setFillGray(gray)
        self.canvas.rect(x0, self.y(bottom), x1 - x0, bottom - top, stroke=0, fill=1)
        self.canvas.setFillGray(0)

    def box(
        self, x0: float, top: float, x1: float, bottom: float, *,
        gray: float | None = None, width: float = GRID_WIDTH,
    ) -> None:
        self.canvas.setLineWidth(width)

        if gray is not None:
            self.canvas.setFillGray(gray)

        self.canvas.rect(x0, self.y(bottom), x1 - x0, bottom - top, stroke=1, fill=0 if gray is None else 1)
        self.canvas.setFillGray(0)

    @contextmanager
    def clipped(self, x0: float, top: float, x1: float, bottom: float) -> Iterator[None]:
        """Everything drawn inside the block is cut at the rectangle."""
        self.canvas.saveState()
        path = self.canvas.beginPath()
        path.rect(x0, self.y(bottom), x1 - x0, bottom - top)
        self.canvas.clipPath(path, stroke=0, fill=0)

        try:
            yield
        finally:
            self.canvas.restoreState()

    def text(
        self, text: str, x0: float, x1: float, baseline_top: float, *,
        size: float, bold: bool = False, align: str = "center", pad: float = 2.5,
    ) -> None:
        """Draw ``text`` inside the horizontal span [x0, x1].

        ``align`` is ``center``, ``right`` or ``left``; ``pad`` is the margin
        from the edge for right and left alignment.
        """
        if not text:
            return

        font = BOLD if bold else REGULAR
        shown = visual(text)
        width = self.canvas.stringWidth(shown, font, size)

        if align == "center":
            x = (x0 + x1) / 2 - width / 2
        elif align == "right":
            x = x1 - pad - width
        else:
            x = x0 + pad

        self.canvas.setFont(font, size)
        self.canvas.drawString(x, self.y(baseline_top), shown)

    def save(self) -> None:
        self.canvas.showPage()
        self.canvas.save()
