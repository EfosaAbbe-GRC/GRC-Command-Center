"""
Benchmark grading -- what a response actually got right, not just whether it refused.

`rag_benchmark.py`'s legacy outcome answers one question: did the model refuse? Anything else
over 20 characters counted as correct. Re-reading the archived answers on 2026-09-27 showed that
was wrong in both directions -- v8 #12 claimed ISO 27001 has ONE mandatory document and scored a
pass; v8 #36 correctly refused (no CSF<->ISO crosswalk in the corpus) and scored a fail; v7 stored
three engine-error messages as answers. See docs/refactors/Benchmark_Grading_refactor.md.

Pure functions, no network, no LLM: grading re-reads stored answer text, so it applies to every
archive retroactively at zero token cost. Imported by rag_benchmark.py (run as a script, so this
directory is on sys.path) and by scripts/rescore_benchmarks.py and the unit tests.

Limitation, stated rather than hidden: closed-list checks test COVERAGE, not correctness. v8 #39
lists the SANS incident-response steps under a NIST 800-61 heading and still passes, because the
right words are present. The 40 queries without an objective check are UNGRADED and count as
passes, exactly as before -- the graded score is an upper bound, not a correctness rate.
"""
import re

# Duplicated from rag_benchmark.py deliberately: archives scored before 2026-08-17 never had this
# check, so re-grading must re-apply it to stored text rather than trust the stored outcome.
ENGINE_FAILURE_MARKERS = (
    "i encountered an error processing your request",
    "security alert: knowledge base integrity check failed",
    "error loading index:",
    "rag engine not initialized",
)

# The model emits narrow no-break spaces and non-breaking hyphens ("Lessons Learned",
# "800‑61"). Without normalising them a correct answer fails its keyword check.
_NORMALISE = str.maketrans({
    " ": " ", " ": " ", " ": " ",
    "‐": "-", "‑": "-", "–": "-", "—": "-",
})

# Closed-list queries: id -> (label, pass bar as fraction of items, item regexes).
# Official sources only. Each item regex is matched case-insensitively.
CLOSED_LIST = {
    1: ("NIST AI RMF core functions", 1.0,
        [r"\bgovern", r"\bmap\b", r"\bmeasure", r"\bmanage"]),
    4: ("NIST AI RMF GOVERN 1-6", 1.0, [
        r"govern\W{0,3}1\b|polic(y|ies),? processes",
        r"govern\W{0,3}2\b|accountabilit",
        r"govern\W{0,3}3\b|diversity|equity|inclusion",
        r"govern\W{0,3}4\b|culture",
        r"govern\W{0,3}5\b|external (ai )?actors|engagement",
        r"govern\W{0,3}6\b|third.part|supply.chain"]),
    6: ("NIST CSF 2.0 implementation tiers", 1.0,
        [r"partial", r"risk.informed", r"repeatable", r"adaptive"]),
    # ISO/IEC 27001:2022 clauses requiring documented information.
    12: ("ISO 27001:2022 mandatory documented information", 0.8, [
        r"scope",                                        # 4.3
        r"(security|isms) polic",                        # 5.2
        r"risk assessment",                              # 6.1.2, 8.2
        r"risk treatment",                               # 6.1.3, 8.3
        r"statement of applicability|\bsoa\b",           # 6.1.3 d
        r"objectives",                                   # 6.2
        r"competen",                                     # 7.2
        r"monitoring and measurement|measurement results",  # 9.1
        r"internal audit",                               # 9.2
        r"management review",                            # 9.3
        r"nonconformit|corrective action"]),             # 10.2
    16: ("EU AI Act risk tiers", 1.0,
         [r"unacceptable|prohibited", r"high.risk", r"limited", r"minimal"]),
    # Only items present in BOTH the 2023 (v1.1) and 2025 editions, so either edition passes.
    18: ("OWASP Top 10 for LLM Applications (common core)", 0.8, [
        r"prompt injection", r"sensitive information disclosure", r"supply chain",
        r"poisoning", r"output handling", r"excessive agency"]),
    26: ("GDPR Art. 5 principles", 1.0, [
        r"lawful", r"purpose limitation", r"minimi[sz]ation", r"accura",
        r"storage limitation", r"integrity|confidentiality", r"accountab"]),
    39: ("NIST SP 800-61r2 incident response phases", 1.0, [
        r"preparation", r"detection|analysis", r"containment|eradication|recovery",
        r"post.incident|lessons learned"]),
}

# Queries whose source is ABSENT from the corpus: refusing is the correct behaviour. Each records
# the corpus state it was verified against -- the expectation stops being true the moment the
# source is added (e.g. #36 once an authoritative crosswalk is ingested), so move it to
# CLOSED_LIST or drop it then.
EXPECT_REFUSAL = {
    36: ("no NIST CSF <-> ISO 27001 crosswalk in corpus", "curated-148 (2026-09-21)"),
    50: ("CISA AI Audit Booklet not in corpus", "curated-148 (2026-09-21)"),
}

PASSING = frozenset({"COMPLETE", "CORRECT_REFUSAL", "UNGRADED_ANSWER"})
ALL_GRADES = ("COMPLETE", "INCOMPLETE", "CORRECT_REFUSAL", "UNSUPPORTED_ANSWER",
              "WRONG_REFUSAL", "UNGRADED_ANSWER", "ERROR")


def grade(query_id, outcome, answer):
    """Return (grade, detail). Never raises on a missing or empty answer."""
    text = (answer or "").translate(_NORMALISE)
    low = text.lower()
    if (outcome or "").startswith("ERROR") or any(m in low for m in ENGINE_FAILURE_MARKERS):
        return "ERROR", ""
    refused = outcome == "INSUFFICIENT_DATA"
    if query_id in EXPECT_REFUSAL:
        return ("CORRECT_REFUSAL", "") if refused else ("UNSUPPORTED_ANSWER", "")
    if refused:
        return "WRONG_REFUSAL", ""
    if query_id in CLOSED_LIST:
        _, bar, items = CLOSED_LIST[query_id]
        hits = [bool(re.search(p, text, re.I)) for p in items]
        missing = [n + 1 for n, h in enumerate(hits) if not h]
        detail = f"{sum(hits)}/{len(hits)}" + (f" missing items {missing}" if missing else "")
        return ("COMPLETE" if sum(hits) / len(hits) >= bar else "INCOMPLETE"), detail
    return "UNGRADED_ANSWER", ""


def summarise(results):
    """Grade a list of stored benchmark results; returns summary fields (does not mutate)."""
    counts = dict.fromkeys(ALL_GRADES, 0)
    for r in results:
        g, _ = grade(r["id"], r.get("outcome"), r.get("answer"))
        counts[g] += 1
    total = len(results)
    passed = sum(counts[g] for g in PASSING)
    checked = total - counts["UNGRADED_ANSWER"] - counts["ERROR"]
    return {
        "graded_pass": passed,
        "graded_percentage": round(passed / total * 100, 2) if total else None,
        "checked_pass": counts["COMPLETE"] + counts["CORRECT_REFUSAL"],
        "checked_total": checked,
        "ungraded": counts["UNGRADED_ANSWER"],
        "grade_counts": counts,
    }
