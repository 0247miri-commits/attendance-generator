"""Conversions between clock times, minutes, decimal hours and money.

Design rule (ADR-003 / ADR-004):
    * Inside the system every duration is an ``int`` number of minutes and
      every amount of money is an ``int`` number of agorot (1/100 shekel).
    * ``Decimal`` is used only to *display* hours with two digits.
    * ``float`` is never used, because it cannot represent values such as
      0.1 exactly (floating-point error, שגיאת נקודה צפה).

Rounding policy (verified on the sample Type B report of January 2023):
    * Each row is rounded on its own for display.
    * Monthly totals and payment are calculated from the *exact minutes* and
      rounded once, at the end. They are NOT the sum of rounded rows.
    * Rounding is half-up (0.5 rounds up, עיגול כלפי מעלה בחצי).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR

_TWO_PLACES = Decimal("0.01")
_WHOLE = Decimal("1")


def parse_clock(text: str) -> int:
    """Convert ``'8:05'`` or ``'08:05'`` to minutes since midnight (485)."""
    parts = text.strip().split(":") if isinstance(text, str) else []

    if len(parts) != 2 or not all(
        part.isascii() and part.isdigit() for part in parts
    ):
        raise ValueError(f"Invalid time {text!r}. Expected HH:MM.")

    hours, minutes = int(parts[0]), int(parts[1])

    if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
        raise ValueError(f"Time out of range: {text!r}.")

    return hours * MINUTES_PER_HOUR + minutes


def format_clock(minutes: int, *, zero_pad_hour: bool = True) -> str:
    """Convert minutes to a clock string.

    Values of 1440 or more (a shift that passes midnight) wrap around, so
    1800 is shown as ``'06:00'``.
    """
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 0:
        raise ValueError("minutes must be a non-negative integer.")

    hours, mins = divmod(minutes % MINUTES_PER_DAY, MINUTES_PER_HOUR)
    hour_text = f"{hours:02d}" if zero_pad_hour else str(hours)
    return f"{hour_text}:{mins:02d}"


def minutes_to_decimal_hours(minutes: int) -> Decimal:
    """Minutes -> decimal hours with two digits, half-up (184 -> 3.07)."""
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 0:
        raise ValueError("minutes must be a non-negative integer.")

    return (Decimal(minutes) / Decimal(MINUTES_PER_HOUR)).quantize(
        _TWO_PLACES, rounding=ROUND_HALF_UP
    )


def decimal_hours_to_minutes(hours: Decimal) -> int:
    """Decimal hours -> whole minutes (3.07 -> 184).

    This conversion is lossy: 3.07 hours is 184.2 minutes, and the display
    value has already been rounded. Use it only when the original entry and
    exit times are not available.
    """
    if not isinstance(hours, Decimal) or not hours.is_finite() or hours < 0:
        raise ValueError("hours must be a finite, non-negative Decimal.")

    return int((hours * MINUTES_PER_HOUR).quantize(_WHOLE, rounding=ROUND_HALF_UP))


def pay_agorot(minutes: int, rate_agorot_per_hour: int) -> int:
    """Exact pay in agorot, rounded half-up once (integers only)."""
    for name, value in (("minutes", minutes), ("rate", rate_agorot_per_hour)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer.")

    return (minutes * rate_agorot_per_hour + MINUTES_PER_HOUR // 2) // MINUTES_PER_HOUR


def format_money(agorot: int) -> str:
    """203859 -> '2,038.59'."""
    if isinstance(agorot, bool) or not isinstance(agorot, int) or agorot < 0:
        raise ValueError("agorot must be a non-negative integer.")

    return f"{agorot // 100:,}.{agorot % 100:02d}"
