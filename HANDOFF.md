# GRC Command Center — Session Handoff (v1.4.0)

## Continue from this point in a new chat

**Date:** July 18, 2026
**Version:** 1.4.0 (Retrieval-Tuned, Re-Ranked, Corpus-Repaired)
**Last Baseline:** 27/27 smoke test · **86.0% RAG accuracy** (v5 benchmark)

---

## What to tell Claude in the new chat

Paste this as your first message:

---

I'm continuing work on the GRC Command Center (v1.4.0). Read `MEMORY.md` (durable facts),
`SESSION.md` (last session's log), and `task.md` (live board) in the project root, then verify the
stack per the boot ritual in MEMORY.md before proposing anything.

Current state: RAG accuracy is at 86% (44%→86% on 2026-07-18 via k=10 + 1000-char chunks +
corpus repair/expansion to 158 docs + cross-encoder re-ranker). The FAISS integrity-signer bug is
fixed. 7 benchmark failures remain, each with a diagnosed root cause and assigned lever.

Next session priorities (pick one):

1. **P2 Judge Calibration** — benchmark results are still flagged `v1_uncalibrated`; build a
   ~15-query human-labeled set. Also resolves whether jitter queries #36/#45 are judge artifacts.
2. **P2 Golden Mapping** — Framework → Control ID structured metadata to crack the EU AI Act
   cluster (#16/#19/#49); the expected path from 86% into the 90s.
3. **P3 Execution Monitor UI** — real-time agent monitor on the WebSocket bus (frontend is healthy
   and the bus is ready; this feature has been deferred since April).

---

## Quick status commands

```powershell
docker compose -f docker-compose-v2.yml ps
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py
cat RAG_Benchmark_Report_v5.md
```
