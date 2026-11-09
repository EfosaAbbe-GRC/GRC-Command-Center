"""Risk register scoring rules (Risk_Register_refactor.md §3, R8): pure functions, no stack needed.

The bands, review cadence and acceptance limits are the organisation's risk criteria
(ISO/IEC 27001:2022 6.1.2 a). They live in one module so a change is one reviewed edit.
"""
import ast
import pathlib
from datetime import date, datetime, timezone

import pytest

from core import risk_scoring as rs
from core.security_config import PROTECTED_TABLES


@pytest.mark.parametrize("score, band", [
    (1, "low"), (4, "low"), (5, "medium"), (9, "medium"),
    (10, "high"), (16, "high"), (20, "critical"), (25, "critical"), (None, None),
])
def test_band_boundaries(score, band):
    assert rs.band(score) == band


@pytest.mark.parametrize("l, i", [(0, 3), (6, 3), (3, 0), (3, 6), (None, 3)])
def test_score_rejects_out_of_range(l, i):
    with pytest.raises(ValueError):
        rs.score(l, i)


def test_score_is_likelihood_times_impact():
    assert rs.score(4, 5) == 20
    assert rs.score(1, 1) == 1


@pytest.mark.parametrize("band, days", [("critical", 90), ("high", 180), ("medium", 365), ("low", 365)])
def test_review_due_follows_band(band, days):
    start = date(2026, 1, 1)
    assert (rs.review_due(start, band) - start).days == days


@pytest.mark.parametrize("band, limit", [("low", 365), ("medium", 365), ("high", 180), ("critical", None)])
def test_acceptance_limits(band, limit):
    assert rs.ACCEPT_MAX_DAYS[band] == limit


def test_critical_residual_cannot_be_accepted():
    assert rs.acceptance_problem("critical", 30) is not None


@pytest.mark.parametrize("band, days, ok", [
    ("low", 365, True), ("low", 366, False), ("medium", 365, True),
    ("high", 180, True), ("high", 181, False), (None, 30, False), ("low", 0, False),
])
def test_acceptance_problem(band, days, ok):
    assert (rs.acceptance_problem(band, days) is None) is ok


@pytest.mark.parametrize("value, expected", [
    ("=HYPERLINK(\"http://x\")", "'=HYPERLINK(\"http://x\")"),
    ("+1", "'+1"), ("-1", "'-1"), ("@SUM(A1)", "'@SUM(A1)"),
    ("\tx", "'\tx"), ("\rx", "'\rx"),
    ("Plain text", "Plain text"), ("", ""), (None, ""), (12, "12"),
])
def test_csv_safe(value, expected):
    assert rs.csv_safe(value) == expected


NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


@pytest.mark.parametrize("kw, status", [
    (dict(closed=True, accepted_until=NOW, treatment="accept", residual_rated=True), "closed"),
    (dict(closed=False, accepted_until=NOW, treatment="accept", residual_rated=True), "accepted"),
    (dict(closed=False, accepted_until=None, treatment="mitigate", residual_rated=True), "treatment_in_progress"),
    (dict(closed=False, accepted_until=None, treatment="avoid", residual_rated=False), "treatment_in_progress"),
    (dict(closed=False, accepted_until=None, treatment="accept", residual_rated=True), "assessed"),
    (dict(closed=False, accepted_until=None, treatment="undecided", residual_rated=True), "assessed"),
    (dict(closed=False, accepted_until=None, treatment="undecided", residual_rated=False), "identified"),
])
def test_status_is_derived_from_the_record(kw, status):
    # R9: an "accepted" status with no acceptance on record must be impossible.
    assert rs.derive_status(**kw) == status


def test_chain_verifier_covers_every_protected_table():
    # R6: scripts/verify_audit_chain.py kept its own list; the two must never drift apart.
    src = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "verify_audit_chain.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    lists = [ast.literal_eval(n.value) for n in ast.walk(tree)
             if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "TABLES" for t in n.targets)
             and isinstance(n.value, (ast.List, ast.Tuple))]
    assert "PROTECTED_TABLES" in names or (lists and set(lists[0]) == set(PROTECTED_TABLES)), \
        "verify_audit_chain.py must cover exactly PROTECTED_TABLES"


def test_risk_events_is_protected():
    assert "risk_events" in PROTECTED_TABLES
