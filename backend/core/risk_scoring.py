"""Risk criteria for the risk register (Risk_Register_refactor.md §3).

ISO/IEC 27001:2022 6.1.2 a) asks the organisation to define its own risk acceptance criteria and
criteria for performing assessments, and 6.1.2 b) asks for consistent, comparable results. This
module is that definition: one place, pure functions, no database imports (unit-tested in CI).
The standard prescribes no matrix; 5 x 5 likelihood x impact is this organisation's choice.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

RATING_MIN, RATING_MAX = 1, 5

# Highest score in each band (5 x 5 products: 1..25).
BANDS = (("low", 4), ("medium", 9), ("high", 16), ("critical", 25))

# Reassessment cadence by band (same cadence as TPRM integration tiers).
REVIEW_DAYS = {"critical": 90, "high": 180, "medium": 365, "low": 365}

# Longest acceptance a risk owner may give, by residual band. None = can't be accepted: treat it.
ACCEPT_MAX_DAYS = {"low": 365, "medium": 365, "high": 180, "critical": None}

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def score(likelihood: Optional[int], impact: Optional[int]) -> int:
    for v in (likelihood, impact):
        if not isinstance(v, int) or isinstance(v, bool) or not RATING_MIN <= v <= RATING_MAX:
            raise ValueError(f"ratings must be integers {RATING_MIN}-{RATING_MAX}")
    return likelihood * impact


def band(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    for name, upper in BANDS:
        if value <= upper:
            return name
    raise ValueError(f"score out of range: {value}")


def review_due(start: date, band_name: str) -> date:
    return start + timedelta(days=REVIEW_DAYS[band_name])


def acceptance_problem(residual_band: Optional[str], days: int) -> Optional[str]:
    """None if a residual risk in this band may be accepted for `days`, else the reason it can't."""
    if residual_band is None:
        return "rate the residual risk before proposing acceptance (ISO/IEC 27001 6.1.3 f)"
    limit = ACCEPT_MAX_DAYS[residual_band]
    if limit is None:
        return f"{residual_band} residual risk can't be accepted; it must be treated"
    if not 1 <= days <= limit:
        return f"{residual_band} residual risk can be accepted for 1-{limit} days"
    return None


def derive_status(*, closed: bool, accepted_until: Optional[datetime], treatment: str,
                  residual_rated: bool) -> str:
    """Status follows from the record's facts (R9); only 'closed' is ever set by hand."""
    if closed:
        return "closed"
    if accepted_until is not None:
        return "accepted"
    if treatment in ("mitigate", "transfer", "avoid"):
        return "treatment_in_progress"
    return "assessed" if residual_rated else "identified"


def csv_safe(value) -> str:
    """Neutralise spreadsheet formulas in exported cells (T9, CSV injection)."""
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text
