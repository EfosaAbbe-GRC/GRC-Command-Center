"""
Unit tests for rag_grading.py -- built from REAL archived benchmark answers, not invented
strings. Every case is a failure the binary scorer actually got wrong. No stack, no network.
See docs/refactors/Benchmark_Grading_refactor.md.
"""
import json
import os

import pytest

from tests.rag_grading import grade, summarise

REPORTS = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "reports")


def _archive(name):
    with open(os.path.join(REPORTS, f"rag_benchmark_results.{name}.json"), encoding="utf-8") as f:
        return {r["id"]: r for r in json.load(f)["results"]}


@pytest.fixture(scope="module")
def v6():
    return _archive("v6_golden_mapping")


@pytest.fixture(scope="module")
def v7():
    return _archive("v7_groq_gptoss120b")


@pytest.fixture(scope="module")
def v8():
    return _archive("v8_curated_corpus")


def _g(r):
    return grade(r["id"], r["outcome"], r["answer"])


def test_v8_q4_incomplete_missing_govern_3_and_6(v8):
    g, detail = _g(v8[4])
    assert v8[4]["outcome"] == "ANSWERED"  # the legacy scorer passed it
    assert g == "INCOMPLETE"
    assert "[3, 6]" in detail


def test_v8_q12_one_document_answer_is_incomplete(v8):
    assert v8[12]["outcome"] == "ANSWERED"
    assert _g(v8[12])[0] == "INCOMPLETE"


def test_v6_q18_describes_the_list_but_names_no_items(v6):
    assert v6[18]["outcome"] == "ANSWERED"
    g, detail = _g(v6[18])
    assert g == "INCOMPLETE"
    assert detail.startswith("0/6")


@pytest.mark.parametrize("qid", [35, 39, 45])
def test_v7_engine_error_stored_as_answered_is_error(v7, qid):
    assert v7[qid]["outcome"] == "ANSWERED"
    assert "encountered an error" in v7[qid]["answer"]
    assert _g(v7[qid])[0] == "ERROR"


def test_v8_q39_unicode_narrow_space_still_matches(v8):
    assert " " in v8[39]["answer"]  # "Lessons Learned"
    assert _g(v8[39]) == ("COMPLETE", "4/4")


def test_expected_refusal_both_directions(v7, v8):
    assert _g(v8[36])[0] == "CORRECT_REFUSAL"
    assert _g(v7[36])[0] == "UNSUPPORTED_ANSWER"


def test_refusing_an_answerable_query_is_wrong_refusal(v8):
    assert v8[26]["outcome"] == "INSUFFICIENT_DATA"
    assert _g(v8[26])[0] == "WRONG_REFUSAL"


def test_query_without_objective_check_is_ungraded():
    assert grade(2, "ANSWERED", "Some long answer text here.") == ("UNGRADED_ANSWER", "")


@pytest.mark.parametrize("answer", [None, "", "   "])
def test_missing_answer_never_raises(answer):
    assert grade(12, "ANSWERED", answer)[0] == "INCOMPLETE"
    assert grade(36, "INSUFFICIENT_DATA", answer)[0] == "CORRECT_REFUSAL"


def test_v8_summary_matches_the_published_regrade(v8):
    s = summarise(list(v8.values()))
    assert (s["graded_pass"], s["checked_pass"], s["checked_total"]) == (46, 6, 10)
    assert s["grade_counts"]["ERROR"] == 0


def test_v7_summary_exposes_three_engine_errors(v7):
    s = summarise(list(v7.values()))
    assert s["grade_counts"]["ERROR"] == 3
    assert s["graded_pass"] == 42
