"""Repeated-sample subset runs of the RAG benchmark (test tooling, not a benchmark variable).

`GRC_BENCH_ONLY` + `GRC_BENCH_REPEAT` + `GRC_BENCH_LABEL` ask chosen questions several times so
sampling noise can be measured (temperature 0.7). A subset run must never overwrite or pass for a
full 50-question result. Unit tests: no stack, no Groq.
See docs/refactors/Golden_Mapping_Leakage_v12_refactor.md §6.
"""
import json
import os
import sys

import pytest

# rag_benchmark.py runs as a script (its own folder on sys.path); mirror that.
sys.path.insert(0, os.path.dirname(__file__))

import rag_benchmark as rb  # noqa: E402


def test_no_subset_variables_means_full_run():
    assert rb.subset_config({}) is None


def test_parses_ids_repeat_and_label(tmp_path):
    cfg = rb.subset_config({"GRC_BENCH_ONLY": "16, 19,49,17,21", "GRC_BENCH_REPEAT": "3",
                            "GRC_BENCH_LABEL": "v12_before"}, cwd=tmp_path)
    assert cfg["ids"] == [16, 19, 49, 17, 21]
    assert cfg["repeat"] == 3
    assert cfg["output"] == str(tmp_path / "rag_benchmark_repeats_v12_before.json")


@pytest.mark.parametrize("env", [
    {"GRC_BENCH_ONLY": "0", "GRC_BENCH_LABEL": "x"},                         # out of range
    {"GRC_BENCH_ONLY": "51", "GRC_BENCH_LABEL": "x"},                        # out of range
    {"GRC_BENCH_ONLY": "16,16", "GRC_BENCH_LABEL": "x"},                     # duplicate
    {"GRC_BENCH_ONLY": "16,abc", "GRC_BENCH_LABEL": "x"},                    # not a number
    {"GRC_BENCH_ONLY": "16", "GRC_BENCH_REPEAT": "0", "GRC_BENCH_LABEL": "x"},
    {"GRC_BENCH_ONLY": "16"},                                                # no label
    {"GRC_BENCH_ONLY": "16", "GRC_BENCH_LABEL": "../results"},               # label escapes
    {"GRC_BENCH_REPEAT": "3"},                                               # repeat without subset
    {"GRC_BENCH_LABEL": "x"},                                                # label without subset
])
def test_rejects_bad_settings(env, tmp_path):
    with pytest.raises(ValueError):
        rb.subset_config(env, cwd=tmp_path)


def test_refuses_to_overwrite_an_existing_repeats_file(tmp_path):
    (tmp_path / "rag_benchmark_repeats_v12_before.json").write_text("{}")
    with pytest.raises(ValueError, match="exists"):
        rb.subset_config({"GRC_BENCH_ONLY": "16", "GRC_BENCH_LABEL": "v12_before"}, cwd=tmp_path)


def test_subset_never_writes_the_full_run_file(tmp_path):
    cfg = rb.subset_config({"GRC_BENCH_ONLY": "16", "GRC_BENCH_LABEL": "a"}, cwd=tmp_path)
    assert os.path.basename(cfg["output"]) != rb.OUTPUT_FILE


def test_saved_subset_is_marked_and_has_no_accuracy(tmp_path):
    cfg = rb.subset_config({"GRC_BENCH_ONLY": "16,19", "GRC_BENCH_REPEAT": "2",
                            "GRC_BENCH_LABEL": "a"}, cwd=tmp_path)
    rows = [{"id": 16, "sample": 1, "outcome": "ANSWERED", "grade": "PASS", "answer": "x" * 30}]
    rb._save_subset(cfg, rows, complete=False)
    data = json.loads((tmp_path / "rag_benchmark_repeats_a.json").read_text())
    s = data["summary"]
    assert s["subset"] is True and s["valid_full_run"] is False
    assert s["ids"] == [16, 19] and s["repeat"] == 2
    assert s["planned"] == 4 and s["completed"] == 1 and s["complete"] is False
    assert "accuracy_percentage" not in s and "graded_percentage" not in s
    assert s["model"] == "openai/gpt-oss-120b" and s["temperature"] == 0.7
    assert data["results"] == rows


def test_rescorer_ignores_repeats_files():
    rescorer = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "rescore_benchmarks.py")
    with open(rescorer, encoding="utf-8") as f:
        src = f.read()
    assert '"rag_benchmark_results.v*.json"' in src


class _Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}

    def json(self):
        return self._body


class _Tok:
    def headers(self, force=False):
        return {"Authorization": "Bearer t"}


@pytest.mark.parametrize("resp, outcome, counted", [
    (_Resp(200, {"response": "A real answer, long enough to count.", "sources": [1, 2]}), "ANSWERED", True),
    (_Resp(200, {"response": "Partly known. INSUFFICIENT_DATA for the rest."}), "INSUFFICIENT_DATA", True),
    (_Resp(200, {"response": "I encountered an error processing your request"}), "ERROR (Engine Failure)", True),
    (_Resp(200, {"response": "short"}), "ERROR (Empty Response)", True),
    (_Resp(500), "ERROR (500)", True),
    (ConnectionError("down"), "ERROR (Timeout/Exc)", False),
])
def test_ask_scores_like_the_full_run_always_has(monkeypatch, resp, outcome, counted):
    """The full run now shares _ask(); its scoring and latency accounting must not change."""
    def fake_post(*a, **k):
        if isinstance(resp, Exception):
            raise resp
        return resp
    monkeypatch.setattr(rb.requests, "post", fake_post)
    got = rb._ask(_Tok(), "q")
    assert got[0] == outcome and got[4] is counted
    summary = {"answered": 0, "insufficient_data": 0, "error": 0}
    rb._count(summary, got[0])
    key = {"ANSWERED": "answered", "INSUFFICIENT_DATA": "insufficient_data"}.get(outcome, "error")
    assert summary[key] == 1 and sum(summary.values()) == 1
