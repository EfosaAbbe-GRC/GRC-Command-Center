"""Golden-mapping triggers must never copy a benchmark question.

A trigger that IS a benchmark question matches it at similarity 1.0, so that question is
guaranteed the verified reference text and its pass measures the lookup table, not the system
(test-set leakage). Pure unit tests: no stack, no model, no Groq. The benchmark questions are
read from rag_benchmark.py with `ast`, so the benchmark is never executed.
See docs/refactors/Golden_Mapping_Leakage_v12_refactor.md.
"""
import ast
import json
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent
MAPPINGS = TESTS.parent / "data" / "golden_mappings.json"
BENCHMARK = TESTS / "rag_benchmark.py"

# Today's highest legitimate trigger-vs-question overlap is 0.54 (v12 draft §1).
NEAR_COPY_JACCARD = 0.80
REQUIRED_KEYS = {"id", "framework", "trigger_phrases", "canonical_context", "source_file"}


def _questions():
    tree = ast.parse(BENCHMARK.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "QUERIES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("QUERIES not found in rag_benchmark.py")


def _mappings():
    return json.loads(MAPPINGS.read_text(encoding="utf-8"))


def _words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _norm(text):
    return " ".join(_words(text))


def _triggers():
    return [(e["id"], t) for e in _mappings() for t in e["trigger_phrases"]]


def test_no_trigger_copies_a_benchmark_question():
    questions = {_norm(q): n for n, q in enumerate(_questions(), 1)}
    copies = [f"{eid}: #{questions[_norm(t)]} {t!r}" for eid, t in _triggers() if _norm(t) in questions]
    assert not copies, "triggers copied from benchmark questions:\n" + "\n".join(copies)


def test_no_trigger_near_copies_a_benchmark_question():
    near = []
    for eid, t in _triggers():
        tw = set(_words(t))
        for n, q in enumerate(_questions(), 1):
            qw = set(_words(q))
            j = len(tw & qw) / len(tw | qw)
            if j >= NEAR_COPY_JACCARD:
                near.append(f"{eid}: #{n} overlap {j:.2f} {t!r}")
    assert not near, "triggers too close to benchmark questions:\n" + "\n".join(near)


def test_every_entry_keeps_at_least_two_triggers():
    thin = [e["id"] for e in _mappings() if len(e["trigger_phrases"]) < 2]
    assert not thin, f"entries with fewer than 2 triggers: {thin}"


def test_mapping_file_is_valid():
    entries = _mappings()
    assert isinstance(entries, list) and entries
    for e in entries:
        missing = REQUIRED_KEYS - e.keys()
        assert not missing, f"{e.get('id', '?')} lacks {sorted(missing)}"
        assert all(isinstance(t, str) and t.strip() for t in e["trigger_phrases"]), e["id"]
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate mapping ids"
