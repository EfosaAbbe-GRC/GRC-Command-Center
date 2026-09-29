"""Local PII redaction for text entering the AI pipeline.

Replaces detected personal data with typed placeholders ("[PERSON]", "[EMAIL_ADDRESS]") before the
text is sent to the LLM provider or written to audit_logs, which is immutable -- anything personal
that reached it could never be erased. Detection runs locally (Microsoft Presidio + spaCy
en_core_web_lg); nothing is sent anywhere to decide what to redact.

It is a risk reduction, not a guarantee: names in unusual forms can be missed, which is why the chat
UI also tells users not to enter personal data. See docs/refactors/PII_Redaction_refactor.md.

Tuning (2026-09-29, measured, not guessed): at SCORE_THRESHOLD 0.5 all 50 benchmark questions and 18
framework references (e.g. "HIPAA 164.312", "PCI DSS v4.0") pass through unchanged. Presidio's own
phone recognizer scores common US formats at only 0.4, so SeparatedPhoneRecognizer adds a stricter
3-3-4 pattern at 0.6 -- lowering the global threshold instead would have redacted "164.312".
"""
import threading

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from core.logger import logger

ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD",
            "IBAN_CODE", "IP_ADDRESS", "US_PASSPORT", "US_DRIVER_LICENSE"]
SCORE_THRESHOLD = 0.5
_OPERATORS = {e: OperatorConfig("replace", {"new_value": f"[{e}]"}) for e in ENTITIES}

# Digits in a 3-3-4 layout with separators, optional +1 / (area code). Not preceded or followed by a
# word character or dot, so section numbers like "164.312" or "800-53" never match.
_PHONE_3_3_4 = r"(?<![\w.])(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?![\w.])"

_lock = threading.Lock()
_analyzer = None
_anonymizer = None


def _engines():
    """Load once. The spaCy model takes up to ~1 min cold, so main.py warms it at startup."""
    global _analyzer, _anonymizer
    if _analyzer is None:
        with _lock:
            if _analyzer is None:
                analyzer = AnalyzerEngine()
                analyzer.registry.add_recognizer(PatternRecognizer(
                    supported_entity="PHONE_NUMBER", name="SeparatedPhoneRecognizer",
                    patterns=[Pattern("phone_3_3_4", _PHONE_3_3_4, 0.6)]))
                _anonymizer = AnonymizerEngine()
                _analyzer = analyzer
                logger.info("PII redaction engine loaded")
    return _analyzer, _anonymizer


def warm_up() -> None:
    """Load the model in the background so the first real question isn't the slow one."""
    try:
        _engines()
    except Exception as e:  # surfaced again, loudly, by redact() on first use
        logger.error("PII redaction warm-up failed", error=str(e))


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Return (redacted_text, {entity_type: count}). An empty dict means nothing was found.

    Raises if the engine can't run. Callers must fail closed: never fall back to sending or
    logging the unredacted text.
    """
    if not text or not text.strip():
        return text, {}
    analyzer, anonymizer = _engines()
    results = analyzer.analyze(text=text, entities=ENTITIES, language="en",
                               score_threshold=SCORE_THRESHOLD)
    if not results:
        return text, {}
    out = anonymizer.anonymize(text=text, analyzer_results=results, operators=_OPERATORS)
    counts: dict[str, int] = {}
    for item in out.items:  # one per replaced span, after overlapping detections are resolved
        counts[item.entity_type] = counts.get(item.entity_type, 0) + 1
    return out.text, counts
