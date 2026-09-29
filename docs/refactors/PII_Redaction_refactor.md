# PII redaction: remove personal data before it reaches the AI provider or the audit log

**Status:** 📝 **DRAFT — awaiting EXECUTE.** Drafted 2026-09-28. Nothing below has been built.
**Decision behind it:** Efosa, 2026-09-28: "remove personal data from questions before they are
logged", extended on recommendation to *before they are sent to Groq*. Recorded as the treatment
for impacts I6/I7 in the ISO 42001 AI System Impact Assessment of this system.
**Costs zero Groq tokens to build and test** (all verification is local), apart from one optional
live chat check.
**Files:** new `backend/core/pii.py`, new `backend/tests/test_pii.py`; edit `backend/main.py`
(chat endpoint), `backend/core/interview_sim.py` (turn submission), `backend/schemas.py`
(`ChatResponse`), `backend/requirements.txt`, `Dockerfile.backend`, `src/components/GRCChatBot.jsx`.
**Effort:** medium. The code is small; the dependency (a language model for name detection) is
the part that needs care.

---

## The problem, in one line

Whatever a user types into the chat is **sent to Groq** and then **written permanently into
`audit_logs`**, where database triggers block any later UPDATE or DELETE. Personal data typed in
by mistake can never be erased, and has already left the machine.

## Why at the front door, not at logging

Redacting only at the logging step would leave the bigger leak (the question sent to Groq)
untouched. One redaction step at the point of entry covers both:

```text
before:  user text ──► Groq ──► answer ──► audit_logs   (personal data in both)
after:   user text ──► redact ──► Groq ──► answer ──► audit_logs   (neither)
```

Basis: GDPR Art. 5(1)(c) data minimisation, Art. 25 data protection by design. The audit log
**stays unchangeable**: no purge route is added, because nothing personal enters it.

## Part A — `backend/core/pii.py` (new)

Built on **Microsoft Presidio** (open source, MIT licence), running **locally**, so detection
itself sends nothing anywhere.

```python
"""Local PII redaction for text entering the AI pipeline.

Replaces detected personal data with typed placeholders ("[PERSON]", "[EMAIL_ADDRESS]") before
the text is sent to the LLM provider or written to audit_logs. Detection runs locally. It is a
risk reduction, not a guarantee: free-text names in unusual forms can be missed, which is why the
chat UI also carries a "do not enter personal data" notice (Part C).
"""
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD",
            "IBAN_CODE", "IP_ADDRESS", "US_PASSPORT", "US_DRIVER_LICENSE"]
SCORE_THRESHOLD = 0.5

_analyzer = None
_anonymizer = None

def redact(text: str) -> tuple[str, dict[str, int]]:
    """Return (redacted_text, {entity_type: count}). Empty dict = nothing found."""
    global _analyzer, _anonymizer
    if _analyzer is None:  # lazy: model loads on first use, not at import
        _analyzer, _anonymizer = AnalyzerEngine(), AnonymizerEngine()
    results = _analyzer.analyze(text=text, entities=ENTITIES, language="en",
                                score_threshold=SCORE_THRESHOLD)
    if not results:
        return text, {}
    out = _anonymizer.anonymize(
        text=text, analyzer_results=results,
        operators={"DEFAULT": OperatorConfig("replace", {"new_value": None})})  # -> "<PERSON>"
    counts: dict[str, int] = {}
    for r in results:
        counts[r.entity_type] = counts.get(r.entity_type, 0) + 1
    return out.text.replace("<", "[").replace(">", "]"), counts
```

*(Final code may differ in detail; the behaviour above is what gets tested.)*
**Deliberately not redacted:** organisation names (`ORGANIZATION` isn't in the list). Framework
bodies (NIST, ISO, AICPA) and vendor names in TPRM questions are what the tool is *for*.

## Part B — call it at the two entry points

1. **`main.py` chat endpoint:** `redacted, found = redact(payload.query)` as the **first line**;
   pass `redacted` to `rag_engine.query()` and to `audit_logger.log_interaction()`. Add
   `redactions: dict` to `ChatResponse` so the UI can tell the user what was removed.
2. **`interview_sim.py` `submit_turn_response`:** redact `payload.response_text` before it is
   stored in `user_response_text` and before it is sent to the grading LLM.

**Not changed:** the `active-auditor` agent (fixed, built-in questions; no user text) and golden
mapping matching (it receives the already-redacted text).

## Part C — chat screen (`GRCChatBot.jsx`)

- A standing line under the input box: *"Do not enter personal or confidential data. Names,
  emails and ID numbers are removed automatically before your question is processed."*
- When `redactions` is non-empty, a small note on that message: *"Removed before sending: 1 name,
  1 email."*

**C2 (treatment for I1/I2 approved by Efosa 2026-09-29; also meets EU AI Act Art. 50(1)):** a per-answer line: *"AI-generated
research aid — verify against the cited source before use."* Screen-only, so it can ship
before or after v9.

## Part D — read-only scan of existing logs (no changes to them)

Run `redact()` over every existing `audit_logs.query` and **report** how many rows contain
detected personal data, by type. The rows themselves are immutable and **won't be touched**. The
point is to know whether I7 has *already* happened, and to record the answer in the impact
assessment.

## Verification (all must pass before commit)

| # | Check | Pass condition |
|---|---|---|
| V1 | Unit tests `test_pii.py`: name, email, phone, SSN, card, IP each redacted; mixed sentence keeps its non-personal words | All pass |
| V2 | **No-harm test:** run `redact()` over **all 50 benchmark questions** | **Zero changes.** Any change is a false positive and blocks the release. This proves the benchmark is unaffected. |
| V3 | Framework terms: "NIST", "ISO 27001 Annex A", "GDPR Article 17", "SOC 2 CC6.1", "Microsoft", "AWS" | Unchanged |
| V4 | Full pytest suite + smoke test | 65/65 + 44/44 still green, plus the new tests |
| V5 | Live: ask the chat a question containing a made-up name and email | The newest `audit_logs` row shows `[PERSON]` / `[EMAIL_ADDRESS]`, not the originals (checked by SQL). Costs ~1 Groq request. |
| V6 | Latency | Median added time per question reported; expected tens of milliseconds against ~3.8 s answers |

## Risks and decisions for Efosa

1. **Language model size (decision).** Presidio finds names using a spaCy model.
   `en_core_web_lg` (~560 MB, Presidio's default, best name detection) vs `en_core_web_md`
   (~40 MB, somewhat weaker). **Recommendation: `lg`**: accuracy is the point of the control, and
   disk is not scarce. The Docker image grows accordingly.
2. **Download path (pre-flight check).** spaCy models install via pip from GitHub release files.
   This PC's firewall already blocks command-line access to huggingface.co. **Before building,
   test that the model downloads inside the Docker build.** If it's blocked, download by hand in
   the browser, as was done for the Whisper model.
3. **Misses are possible.** Unusual names, names in lower case, or ID formats outside the list.
   Part C's notice is the second layer. Documented as residual risk in the impact assessment.
4. **Sequencing with v9 (recommendation).** Deploy **after** the v9 benchmark runs, so v9 remains
   a clean one-variable measurement of the golden-mapping change. V2 should show redaction doesn't
   alter benchmark questions anyway, but keeping the order clean costs nothing.
5. **Not retroactive.** Existing audit rows stay as they are (by design). Part D reports on them.

## Rollback

Single commit. Revert it and rebuild the backend image. No database migration, no data changes.
