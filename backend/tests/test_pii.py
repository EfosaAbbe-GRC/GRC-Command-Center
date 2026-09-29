"""
PII redaction -- core/pii.py. See docs/refactors/PII_Redaction_refactor.md.

Needs the spaCy model, which lives in the backend image. Tests aren't baked into the image
(.dockerignore), so copy them in and run from /app (the logger writes ./logs there):
    docker exec -u root grc-backend-test sh -c 'rm -rf /tmp/t && mkdir -p /tmp/t'
    docker cp backend/tests grc-backend-test:/tmp/t/tests
    docker exec -w /app -e PYTHONPATH=/app:/tmp/t grc-backend-test \
        python -m pytest -q -p no:cacheprovider --rootdir /tmp/t /tmp/t/tests/test_pii.py
(Git Bash on Windows: set MSYS_NO_PATHCONV=1 first.) Without presidio installed, the module skips.

The no-harm test (every benchmark question passes through unchanged) is the release gate: a false
positive there would silently change what the benchmark measures.
"""
import os
import sys

import pytest

pytest.importorskip("presidio_analyzer")

# rag_benchmark.py is written to run as a script (its own folder on sys.path); mirror that.
sys.path.insert(0, os.path.dirname(__file__))

from core.pii import redact  # noqa: E402
from rag_benchmark import QUERIES  # noqa: E402


@pytest.mark.parametrize("text, entity, original", [
    ("Our vendor contact Maria Gonzalez hasn't replied", "PERSON", "Maria Gonzalez"),
    ("Send it to john.smith@acme.com today", "EMAIL_ADDRESS", "john.smith@acme.com"),
    ("Call 555-201-3344 about the report", "PHONE_NUMBER", "555-201-3344"),
    ("Call +1 (415) 555-0132 after lunch", "PHONE_NUMBER", "(415) 555-0132"),
    ("reach me on 415.555.0132", "PHONE_NUMBER", "415.555.0132"),
    ("SSN 536-22-8714 appeared in the log", "US_SSN", "536-22-8714"),
    ("Card 4111 1111 1111 1111 was stored unencrypted", "CREDIT_CARD", "4111 1111 1111 1111"),
    ("User logged in from 192.168.1.20", "IP_ADDRESS", "192.168.1.20"),
])
def test_personal_data_is_redacted(text, entity, original):
    out, counts = redact(text)
    assert original not in out
    assert f"[{entity}]" in out
    assert counts.get(entity, 0) >= 1


def test_non_personal_words_survive():
    out, _ = redact("Priya Patel approved the risk acceptance for the SOC 2 exception")
    assert "Priya Patel" not in out
    assert out.endswith("approved the risk acceptance for the SOC 2 exception")


def test_all_benchmark_questions_pass_through_unchanged():
    changed = [(q, redact(q)[0]) for q in QUERIES if redact(q)[0] != q]
    assert len(QUERIES) == 50
    assert changed == []


@pytest.mark.parametrize("text", [
    "NIST SP 800-53 Rev 5 control AC-2",
    "ISO/IEC 27001:2022 Annex A 5.23",
    "GDPR Article 17 right to erasure",
    "SOC 2 CC6.1 and CC7.2",
    "PCI DSS v4.0 requirement 8.3.6",
    "HIPAA 164.312(a)(1)",
    "Regulation (EU) 2024/1689 and 2016/679",
    "NIST SP 800-171r3 3.1.1",
    "What does Microsoft Azure Policy do?",
    "OWASP LLM01:2025 prompt injection",
])
def test_framework_references_are_not_redacted(text):
    assert redact(text) == (text, {})


def test_empty_and_blank_input():
    assert redact("") == ("", {})
    assert redact("   ") == ("   ", {})
