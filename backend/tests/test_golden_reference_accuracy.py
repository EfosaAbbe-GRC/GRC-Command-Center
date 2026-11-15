"""Golden-mapping reference texts must not carry the errors found in the tier-1 audit.

The text of each entry is shown to the model labelled "verified reference", and the model repeats
it (v12: every #19/#49 sample repeated the errors). These tests pin the specific errors found on
2026-11-15 so they can't come back, and require every entry to say what it was checked against.
They can't prove a text is right; the claim-by-claim read in the draft does that.
Pure unit tests: no stack, no model, no Groq, no PDF.
See docs/refactors/Golden_Reference_Correction_refactor.md.
"""
import json
import re
from datetime import date
from pathlib import Path

import pytest

MAPPINGS = Path(__file__).resolve().parent.parent / "data" / "golden_mappings.json"

# Page counts of the corpus PDFs (pypdf 6.5.0, 2026-11-15), so no PDF is needed at test time.
PDF_PAGES = {
    "EU AI ACT 2024_Doc.pdf": 144,
    "AI RMF 1.0.pdf": 48,
    "OWASP Top 10 for LLM Applications 2025.pdf": 45,
    "GDPR_Regulation_Text.pdf": 88,
    "ISO 27001-2022 BookLet.pdf": 26,
}


def _entries():
    return {e["id"]: e for e in json.loads(MAPPINGS.read_text(encoding="utf-8"))}


def _text(entry_id):
    return _entries()[entry_id]["canonical_context"]


def _flat(text):
    """Lower-case, single spaces, plain hyphens, so phrasing checks ignore layout."""
    text = text.replace("–", "-").replace("‑", "-").replace("‐", "-")
    return " ".join(text.lower().split())


def test_every_entry_has_a_verification_record():
    problems = []
    for e in _entries().values():
        v = e.get("verified")
        if not isinstance(v, dict):
            problems.append(f"{e['id']}: no 'verified' record")
            continue
        if v.get("against") != e["source_file"]:
            problems.append(f"{e['id']}: verified.against != source_file")
        try:
            date.fromisoformat(v.get("on", ""))
        except ValueError:
            problems.append(f"{e['id']}: verified.on is not an ISO date")
        if not v.get("method"):
            problems.append(f"{e['id']}: verified.method is empty")
    assert not problems, problems


# (entry, wrong phrase) pairs from the audit, draft §3.1-§3.3.
KNOWN_ERRORS = [
    ("EU_AI_ACT_RISK_TIERS", "title ii"),                      # R1: it's Chapter II
    ("EU_AI_ACT_RISK_TIERS", "narrow and limited nature"),     # R2: recital 53 / Art. 6(3)
    ("EU_AI_ACT_GPAI_GENERATIVE", "incident reporting to the commission"),  # G4: AI Office
    ("EU_AI_ACT_GPAI_GENERATIVE", "does not name"),            # G1: recitals 99 and 105 do
    ("EU_AI_ACT_OPEN_SOURCE", "or as a general-purpose ai model with systemic risk (article 51)"),  # O1/O5
    ("EU_AI_ACT_OPEN_SOURCE", "fall outside several of the act's obligations"),  # O2
]


@pytest.mark.parametrize("entry_id,phrase", KNOWN_ERRORS)
def test_eu_known_errors_are_gone(entry_id, phrase):
    assert phrase not in _flat(_text(entry_id)), f"{entry_id} still says {phrase!r}"


def test_eu_citations_have_no_known_errors():
    blob = _flat(json.dumps({k: _entries()[k]["citations"] for k in (
        "EU_AI_ACT_RISK_TIERS", "EU_AI_ACT_GPAI_GENERATIVE", "EU_AI_ACT_OPEN_SOURCE")}))
    for wrong in ("articles 52-56", "recital (whitepaper", "gpai systemic-risk carve-out"):
        assert wrong not in blob, f"citation still says {wrong!r}"


def test_open_source_names_the_real_exceptions():
    t = _flat(_text("EU_AI_ACT_OPEN_SOURCE"))
    for needed in ("article 2(12)", "article 5", "article 50", "53(2)", "54(6)", "25(4)",
                   "copyright", "training-content summary"):
        assert needed in t, f"open-source entry lacks {needed!r}"
    assert "article 51" not in t, "Art. 51 classifies systemic-risk models; it isn't the exemption"


def test_gpai_lists_all_duties():
    t = _flat(_text("EU_AI_ACT_GPAI_GENERATIVE"))
    for needed in ("article 53(1)", "(a)", "(b)", "(c)", "(d)", "article 55(1)",
                   "assess and mitigate possible systemic risks", "ai office", "article 50(2)",
                   "recital 99", "article 3(66)"):
        assert needed in t, f"GPAI entry lacks {needed!r}"


def test_risk_tiers_uses_the_regulations_structure():
    t = _flat(_text("EU_AI_ACT_RISK_TIERS"))
    for needed in ("chapter ii", "article 6(3)", "article 50", "article 95", "article 4"):
        assert needed in t, f"risk-tiers entry lacks {needed!r}"


def test_cited_pages_exist():
    problems = []
    for e in _entries().values():
        limit = PDF_PAGES.get(e["source_file"])
        assert limit, f"{e['id']}: unknown source_file {e['source_file']!r}"
        for c in e.get("citations", []):
            for n in re.findall(r"\d+", str(c.get("pdf_pages", ""))):
                if not 1 <= int(n) <= limit:
                    problems.append(f"{e['id']}: page {n} > {limit}")
    assert not problems, problems
