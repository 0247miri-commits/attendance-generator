"""Filesystem locations used across the project."""

from pathlib import Path

# src/attendance_generator/paths.py -> the project root is two levels above.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FONT_DIR = PROJECT_ROOT / "fonts"
