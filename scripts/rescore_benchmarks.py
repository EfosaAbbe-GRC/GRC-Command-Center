#!/usr/bin/env python3
"""
Re-grade every archived RAG benchmark run with backend/tests/rag_grading.py.

Zero LLM calls: it re-reads the answer text stored in each archive. Archives are READ ONLY --
the only file written is docs/reports/benchmark_regrade_<YYYY-MM-DD>.json, so the originals stay
byte-identical (archive-don't-delete). Partial and invalid runs are listed but not scored.

    python scripts/rescore_benchmarks.py

See docs/refactors/Benchmark_Grading_refactor.md.
"""
import datetime
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "docs", "reports")
sys.path.insert(0, os.path.join(ROOT, "backend", "tests"))
from rag_grading import grade, summarise  # noqa: E402


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(REPORTS, "rag_benchmark_results.v*.json"))):
        name = os.path.basename(path)[len("rag_benchmark_results."):-len(".json")]
        with open(path, encoding="utf-8") as f:
            results = json.load(f)["results"]
        if len(results) != 50 or "PARTIAL" in name or "INVALID" in name:
            print(f"{name:<40} skipped ({len(results)} results; not a complete valid run)")
            continue
        s = summarise(results)
        legacy = sum(r["outcome"] == "ANSWERED" for r in results)
        per_query = {r["id"]: grade(r["id"], r.get("outcome"), r.get("answer")) for r in results}
        rows.append({
            "archive": name,
            "legacy_answered": legacy,
            **s,
            "checked_queries": {i: {"grade": g, "detail": d}
                                for i, (g, d) in per_query.items() if g != "UNGRADED_ANSWER"},
        })
        print(f"{name:<22} legacy {legacy:>2}/50  graded {s['graded_pass']:>2}/50  "
              f"errors {s['grade_counts']['ERROR']}  checkable {s['checked_pass']}/{s['checked_total']}")

    out = os.path.join(REPORTS, f"benchmark_regrade_{datetime.date.today().isoformat()}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                   "grader": "backend/tests/rag_grading.py",
                   "runs": rows}, f, indent=2)
    print(f"\nWrote {os.path.relpath(out, ROOT)} (archives untouched)")


if __name__ == "__main__":
    main()
