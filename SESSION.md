# Session Log — 2026-08-05 ("Golden Mapping Closes the EU AI Act Cluster; a Scorer Bug Traced Back Through Every Prior Run")

**Outcome:** Picked RAG P2 Golden Mapping off the post-TPRM pivot-point menu (over Judge
Calibration and Execution Monitor UI). Diagnosed the EU AI Act cluster (#16/#19/#49) against the
actual source PDF rather than trusting the v5 report's summary alone, drafted and EXECUTED a
query-time Golden Mapping layer, and closed all three targeted failures. A 4th flip in the same
benchmark run turned out to be a scorer artifact, not a real fix — asked to review it (and the PDF
defect) before committing anything, which led to tracing the exact same scorer bug back through
**every prior benchmark run this project has ever recorded** and correcting the whole historical
trajectory. Final, corrected number: **84.0% → 92.0%** (both the pre- and post-Golden-Mapping
figures moved down 2pts from what had been reported — see below, nothing about the retrieval work
itself changed).

## What happened, in order

1. **Boot-ritual verification first** (per HANDOFF.md instruction): stack was already up, readiness
   green, smoke 42/42, pytest 32/32 — matched docs exactly. Also found, incidentally, that
   `grc-frontend` has been reporting Docker-healthcheck "unhealthy" for its entire 40-hour uptime —
   traced to an IPv6/IPv4 loopback mismatch in the healthcheck itself (see MEMORY.md gotcha); the
   app is actually fine. Not fixed, just documented — out of scope for today's focus.
2. **Root-caused #16/#19/#49 against the real PDF**, not just the v5 report's one-line diagnosis:
   pulled actual extracted text from `EU AI ACT 2024_Doc.pdf` via `pypdf` to confirm exact article
   citations (Article 5 unacceptable risk, Article 6 high-risk, Article 50 limited-risk/
   transparency, Article 95 voluntary codes; Articles 51-56 GPAI/"general-purpose AI model" as the
   Act's actual term for what the benchmark calls "ChatGPT"; the open-source licence exemption
   clause). Also found, along the way, that this specific PDF's text extraction systematically
   injects spaces inside words (`"Ar ticle 9"`) — a real, previously undocumented corpus-quality
   defect, deliberately **not** fixed this session (bigger lever, would need re-extraction/
   re-ingestion of at least this file) — flagged in MEMORY.md as a future candidate.
3. **Drafted `Golden_Mapping_refactor.md`** per GOVERNANCE §4.A draft-first — before proposing a
   similarity threshold, actually ran the real `all-MiniLM-L6-v2` model (inside the running
   `grc-backend` container, read-only, `MSYS_NO_PATHCONV=1` needed for `docker cp`/`exec` on this
   Windows/Git-Bash setup — new gotcha, now in MEMORY.md) against all 50 benchmark queries to find
   the actual closest cross-framework false-positive risk (a NIST query at 0.648 cosine similarity)
   before picking 0.70 as the threshold — a data-backed number, not a guess.
4. **User replied EXECUTE.** Implemented: new `backend/data/golden_mappings.json` (3 hand-curated,
   source-cited entries), `rag.py` gained `_load_golden_mappings`/`_match_golden_mappings`
   (query-time cosine-similarity match against cached trigger-phrase embeddings, reusing the
   already-loaded embedding model — no new ML dependency). **One necessary deviation from the
   draft, found mid-implementation:** `RAGEngine` had no persistent `self.embeddings` attribute
   anywhere (every call site created its own local instance) — added a small `_get_embeddings()`
   cache rather than touch existing ingestion/query code paths, to keep blast radius additive-only.
   `numpy` promoted from transitive to declared dependency in `requirements.txt`.
5. **Rebuilt backend only** (no re-ingestion — this doesn't touch the FAISS index). Smoke **42/42**,
   pytest **32/32**, unchanged from pre-deploy baseline.
6. **Re-ran the full 50-query benchmark**, archived as `rag_benchmark_results.v6_golden_mapping.json`.
   Result: 94.0% raw (47/50). Verified the mechanism actually fired for #16/#19/#49 by reading the
   answer text itself — each one reproduces the curated `canonical_context` near-verbatim, not just
   a coincidental score flip. Zero regressions among the 43 previously-passing queries.
7. **Caught a 4th flip (#6, CSF tiers) that did NOT belong to this change:** Golden Mapping has no
   NIST CSF entry — reading the actual answer showed it's the same substantively-incomplete response
   v5 gave (Tier 1 only, explicit inline `INSUFFICIENT_DATA` for Tiers 2-4), just phrased so the
   literal string `INSUFFICIENT_DATA` no longer led the response — `rag_benchmark.py`'s scorer only
   checked `.startswith("INSUFFICIENT_DATA")`. Reported both numbers (94% raw / 92% attributable)
   rather than taking credit for what looked, at the time, like a one-off scorer quirk.
8. **User asked to review this and the PDF defect before committing anything.** Checking blast
   radius on the PDF issue first: confirmed via producer/creator metadata across all 158 corpus
   PDFs that `EU AI ACT 2024_Doc.pdf` is the **only** file with this producer — isolated, not
   systemic. Then, scanning every archived `rag_benchmark_results.v*.json` for the same
   `.startswith()` failure pattern found it wasn't a v6-only fluke: **v1 (#31, SOC 2), v2 (#6, CSF
   tiers), v3/v4/v5 (#35, Three Lines of Defense) all had exactly one identically-shaped false
   `ANSWERED`** — a real partial answer with an inline refusal for the unanswerable part. Every
   historical topline this project has ever reported (44/72/78/82/86/94%) had been inflated by one
   query, this whole time.
9. **User chose: fix the scorer + correct the old reports.** Changed `rag_benchmark.py`'s check to a
   substring match. Reclassified the affected entry in every archived JSON (plus the live
   `rag_benchmark_results.json`) with an added `_correction_note`/`_corrected_2026-08-05` field —
   nothing silently overwritten. Updated `RAG_Benchmark_Report.md` (v1), `_v2.md`, `_v3.md`, `_v5.md`,
   and `_v6.md` with correction callouts and the true numbers: **42/70/76/80/84/92%**. The trend and
   every inter-run delta (+28pts, re-ranker's +4 net) are exactly unchanged — only absolute values
   moved, each by one query.
10. **Found, but explicitly did NOT fix (separate, unauthorized scope):** re-checking v1's report
    against its own raw archive to correct the scorer bug's specific effect surfaced an unrelated
    problem — the report's category-breakdown table (NIST/ISO/EU AI Act/GDPR/etc.) doesn't match the
    archive at all, independent of the startswith bug (e.g. NIST row says 3/8 answered, archive says
    5/8). Flagged in the report's correction note and in MEMORY.md; not audited further, not
    resolved — a bigger, separate task than what was asked.

## Two things found and deliberately left unfixed (documented, not silently dropped)

- The PDF text-mangling defect (`"Ar ticle 9"`) — confirmed isolated to one corpus file, but fixing
  properly needs a new extraction dependency (`pdfplumber`/`PyMuPDF`, neither currently installed)
  plus re-ingestion. User chose to park this.
- The v1 report's category-breakdown-table discrepancy (found in step 10 above) — a different,
  unaudited issue from the scorer bug that was actually fixed. Not yet checked whether v2/v3/v5's
  category tables have the same problem.

## Current deployed state

- RAG accuracy: **92%** (corrected; up from a corrected 84% baseline — see MEMORY.md's "Key
  numbers" for the full before/after table), TPRM unchanged (still fully complete per 2026-08-04).
  Smoke 42/42, pytest 32/32.
- New file: `backend/data/golden_mappings.json`. Modified: `backend/core/rag.py`,
  `backend/requirements.txt` (numpy declared), `backend/tests/rag_benchmark.py` (scorer fix), all
  6 `rag_benchmark_results.v*.json` archives + the live one, and 5 `RAG_Benchmark_Report*.md` files.
- **Not browser-verified** — this change has no UI surface (query-path only), so N/A this time,
  unlike the outstanding TPRM UI-surface browser-verification gap (still open from 2026-08-04).

## Next session menu

1. **RAG P2 Judge Calibration** or **RAG P3 Execution Monitor UI** — the other two items from the
   post-TPRM pivot menu, still both live options.
2. **TPRM Tier 4** (opportunistic, still low-priority) / **browser-verify TPRM's UI surfaces**
   (still outstanding from 2026-08-04) — unchanged, not touched this session.
3. The v1 category-breakdown-table discrepancy (step 10 above) — worth a dedicated audit pass if
   these numbers are ever cited somewhere that matters (interview prep, resume-adjacent material).
   Check whether v2/v3/v5 have the same issue while at it.
4. The EU AI Act PDF extraction defect — parked, not blocking; raise only if corpus/harness hygiene
   becomes a priority.
5. The frontend Docker-healthcheck false-"unhealthy" (IPv6/IPv4 mismatch) — cosmetic only, fix is
   a one-line `HEALTHCHECK` change to `wget http://127.0.0.1:3006/` if ever worth doing.

---

# Session Log — 2026-08-03/04 ("Closing Out the TPRM Roadmap: Tier 2 → Tier 3, Start to Finish")

**Outcome:** Pushed the prior session's held-back commit, then executed and shipped the entire
remaining TPRM backlog in one continuous push — Tier 2's last item (2.3) and all three Tier 3
items (3.1, 3.2, 3.3). **The full TPRM roadmap (Tier 1 + Tier 2 + Tier 3) is now complete.** Found
and fixed three real, previously-undiscovered bugs along the way, none of them things this session
set out to look for.

## What happened, in order

1. **Pushed `f0bff91`** (Tier 1 + 2.4/2.1/2.2, held back at prior session's close).
2. **2.3 — Vendor-level risk rollup:** `_recompute_vendor_tier` (max-severity across a vendor's
   integrations) hooked into `create_integration` + both `approve_integration` paths. Frontend
   vendor-portfolio strip. Closes Tier 2.
3. **3.1 — Reassessment surfacing:** event-driven WebSocket broadcast (no backend scheduler exists
   in this repo, and none was added — confirmed with the user rather than assumed) nudges
   connected terminals to re-fetch `/reassessments/due` + `/acceptances/expiring`. Header badge +
   expandable panel. **Bug found:** `OpsTerminal.jsx`'s WebSocket had never actually connected —
   `user?.access_token` doesn't exist on the auth context; the real token lives in `api.js`'s
   private `tokenStore`. Fixed via a new `api.getAccessToken()`.
4. **3.2 — CSV assessment export:** `GET /tprm/export`, three-section CSV mirroring
   `/compliance/export`'s pattern. **Bug found:** that same `/compliance/export`'s existing
   "Export CSV Report" button used `window.location.href`, which sends no auth header — it had
   been silently 401ing. Fixed via a new shared `api.downloadFile()` helper.
5. **3.3 — Evidence linkage to `evidence_chain`:** the largest item. Real architecture decision
   (confirmed with the user before drafting): full file upload, not a lighter hash-reference
   alternative — this codebase had zero prior upload endpoints anywhere. New append-only
   `StageEvidenceLink` table, `POST/GET .../stages/{stage_id}/evidence`, `AuditLogger.log_evidence`
   widened to return the row id and propagate exceptions instead of swallowing them. **Bug found:**
   the new Docker volume for evidence storage mounted root-owned on first creation (Windows/WSL2
   Docker Desktop inherits ownership into a fresh named volume only from a path that already
   exists, chowned, in the image — `data/tprm_evidence` wasn't in `Dockerfile.backend`'s `mkdir`
   line, unlike `faiss_index`, which is why that one already worked). Fixed the Dockerfile,
   recreated the volume, and specifically proved durability (upload → rebuild → file and DB row
   both survived) rather than just trusting the fix.

Every item followed the same loop: draft artifact → confirm design calls via targeted questions →
apply → rebuild → smoke + pytest → close out docs/memory → commit → push (all explicitly confirmed
by the user each time, per GOVERNANCE §4.A).

## The three bugs, as a pattern

All three were variants of the same root cause: **a frontend action that bypassed `api.js`'s
central auth-header plumbing** (a raw `window.location.href`, a WebSocket built with the wrong
token source) or **an infra assumption that didn't hold under the non-root container user** (a
volume mount that needed the image to already own the path). None were things any Tier item asked
for — all three surfaced from reading the code adjacent to what was actually being built, then
verifying rather than assuming it worked. Worth the same scrutiny next time new frontend
download/upload/telemetry code — or a new Docker volume — gets added.

## One process correction worth remembering

Running `pytest backend/tests/ -v` from the repo root (instead of `cd backend && pytest -v`)
silently skips `backend/pyproject.toml`'s `--ignore=tests/smoke_test.py` rule (that ignore path is
relative to `backend/` as pytest's rootdir). This produced a false-alarm regression signal once
this session (2 `ReadTimeout`s that looked exactly like a code-caused failure) before being traced
to the invocation, not the change. Always run pytest from inside `backend/` in this repo.

## Current deployed state

- All TPRM roadmap work is live and pushed: `f0bff91`, `5f4e59c` (2.3), `21c3c3b` (3.1), `3abce53`
  (3.2), `70d5e84` (3.3). Repo fully in sync with `origin/main`.
- Smoke test: **42/42**. Pytest: **32/32** (5 IAM + 27 TPRM), run from `backend/`.
- New Docker volume `grc-tprm-evidence` (evidence file storage), correctly owned by `grcuser`.
- **Not browser-verified this session at all** — no browser-automation tool was available. Every
  new UI surface (2.3's vendor strip, 3.1's reassessment badge, 3.2's export button, 3.3's evidence
  upload/list panel) was verified via API/curl/WS-client checks only. Worth an actual browser pass
  next time one's available, even though nothing here is expected to be broken.

## Next session menu

TPRM's roadmap is exhausted — this is an open pivot point, not a "next item per the plan" like
every prior session this arc.

1. **RAG backlog** (parked behind TPRM since 2026-08-02, never actually abandoned): P2 Judge
   Calibration (results still flagged `v1_uncalibrated`), P2 Golden Mapping (the expected path from
   86% into the 90s, targets the EU AI Act cluster), or P3 Execution Monitor UI (deferred since
   April, frontend/WS bus both ready). Any of the three is a reasonable default to raise
   proactively, since there's no more TPRM backlog to fall back on.
2. **TPRM Tier 4** (opportunistic, explicitly low-priority): test-data hygiene (smoke/pytest have
   been accumulating vendors/integrations across many runs — hundreds by now), frontend component
   tests (none exist project-wide).
3. **Browser-verify the four TPRM UI surfaces** above, once a browser-automation tool is available.
