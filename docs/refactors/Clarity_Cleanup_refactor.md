# Clarity cleanup: stale docs, dead code, misplaced files

**Status:** **EXECUTED 2026-10-25** (EXECUTE from Efosa). Decisions, all as recommended: **D1 (a)**
retire the skills (archived unchanged; GOVERNANCE §B amended), **D2 (b)** the Mufasa script went
to the owner's workspace `_archive/` (byte-identical copy verified before `git rm`), **D3** fixed
`run_dashboard.bat`. Every finding below was checked against the files on 2026-10-25, not carried
over from the quick list made during the security sweep.

**Verified:** no stale strings left in code/README/CLAUDE (`ingest_documents`, `DATABASE_PATH`,
`18,337`, `v1.2.0`, `65/65`). Both backends rebuilt and healthy. Readiness 4/4. The API reports
`1.5.0`. `trigger_ingest.py`, `debug_imports.py`, `.env` and `pytest_output.txt` are all absent from
the image. pytest (all but `test_interview_sim.py`): **76 passed, 1 skipped**, unchanged.

**Found during execution: OneDrive restores deleted files in this folder.** Everything deleted
locally on 2026-10-25 around 01:30 reappeared at 18:20 with its *original* timestamps:
`backend/.env`, the legacy `docker-compose.yml`, `bench_run.err` and two SQLite scratch files. The
re-created `.env` was an online-only placeholder, meaning the local deletion never reached the
cloud copy. **No live secret was exposed:** every value in that file had been rotated or was
unused. All were deleted again and checked at the end of the session. Consequence for every future
"delete": in this folder a deletion isn't final until it's confirmed later. Any secret file here,
including the live root `.env`, also exists in the owner's OneDrive cloud and its version history.

**Why it matters:** each item either tells a reader something false, looks alive but isn't, or
lives in the wrong project. None of them is a security hole. Together they're what made an outside
marketplace pitch, and a first read of this repo, land on April-era material.

**Benchmark isolation:** nothing here touches the live RAG path (retrieval, prompt, index, golden
mappings). The one `rag.py` change deletes a function nothing calls. v12's one-variable rule is
unaffected, and no re-ingest is needed.

---

## A. Text that tells a reader something false

| ID | Where | What it says | Reality | Change |
| --- | --- | --- | --- | --- |
| A1 | `.agents/skills/*/SKILL.md` (4 files, 2026-04-10) | `active-auditor`: "Do not write directly to the SQLite `grc_audit.db`" | PostgreSQL since April 11. No code reads these files (`git grep .agents` → nothing outside docs). | **Owner decision D1** |
| A2 | `CLAUDE.md` | Architecture block "GRC Command Center **v1.2.0**". File Structure lacks this month's files. "Backend Dev: `python main.py`" | Version is 1.5.0. Missing: `core/security_config.py`, `core/login_throttle.py`, `tests/_creds.py`. The backend now refuses to start without the root `.env` secrets. | Fix the header; add the three files; note the `.env` prerequisite; add one Audit History line for Aug–Oct (benchmarks v8–v11, PII redaction, security hardening). Historical lines (86%, 27/27) stay: they are history, already labelled stale. |
| A3 | `README.md` lines 27, 143 | "65/65 unit tests" | 88 passed + 1 skipped (after the 2026-10-25 additions) | Update both |
| A4 | `main.py` `/ingest` broadcast | "Vault rebuild initiated across **18,337** potential splits." | A months-old count; the live index is 16,998 chunks | `"Vault rebuild initiated."` A hard-coded count goes stale on every re-ingest. |
| A5 | `config.py` | `VERSION = "1.0.0"` (logged at startup, shown in the OpenAPI docs) | 1.5.0 | `"1.5.0"` |

## B. Looks alive, isn't

| ID | What | Evidence it's dead | Change |
| --- | --- | --- | --- |
| B1 | `RAGEngine.ingest_documents()` (`rag.py:100`) | Called from nowhere. Its recursive `**/*.pdf` glob would pull `Excluded Docs/` back into the index, undoing v11 and the August curation. **Already found 2026-09-21** (SESSION.md, "worth knowing the dead function is a trap") **and left in place.** | Delete the method. The live path, `initialize_index`, is untouched. |
| B2 | `config.py` `DATABASE_PATH` (SQLite) | No reader anywhere | Delete |
| B2b | `config.py` `DATABASE_URL` default | Embeds the old public Postgres password (rotated 2026-10-25, so dead, but still misleading) | Default without a password: `postgresql+asyncpg://grc_admin@localhost:5432/grc_audit`. Compose always supplies the real URL. |
| B3 | `backend/trigger_ingest.py` | Wrong port (8000), wrong path (`/api/ingest`, pre-v1), no auth, so it can't work. Also copied into the image. | `git rm` (history keeps it) |
| B4 | `backend/debug_imports.py` | A one-off April LangChain import probe | `git rm` |
| B5 | `scripts/verify_rag.py` | Reads `backend/data/grc_audit.db` via `sqlite3` and calls `/chat` unauthenticated. Dead twice over. | `git rm` |
| B6 | `scripts/run_dashboard.bat` | **Broken since the 2026-08-21 move into `scripts/`.** `cd /d "%~dp0"` now lands in `scripts/`, where there's no `package.json`. | Fix: `cd /d "%~dp0.."` (one line), so it still launches the Vite dev server from the repo root |

## C. In the wrong project

| ID | What | Change |
| --- | --- | --- |
| C1 | `scripts/sim_market_data.ps1`: a Mufasa market-data simulator with hard-coded Mufasa paths, unreferenced here | `git rm` here. **This is the only copy** (the Mufasa folder has none), so it moves rather than disappears: **owner decision D2** says where. |

## D. Local traps (untracked; not in git, so no commit)

| ID | What | Change |
| --- | --- | --- |
| D1 | `faiss_index/` (39 MB, April). The HANDOFF warns it's a decoy, because the live index is the `grc-faiss` volume. **New: `backend/tests/create_snapshot.py` copies this folder**, so a snapshot taken today would silently capture the April index. | Move it to the workspace `_archive/faiss_index_2026-04_decoy/`. `create_snapshot.py` then fails loudly instead of snapshotting the wrong index. Re-pointing it at the volume is a later item. Drop the HANDOFF warning once the folder is gone. |
| D2 | `backend/backend/data/grc_audit.db` (untracked since `fa6ee8d`, now ignored) | Move to the workspace `_archive/grc_audit_db_2026-04/` |

---

## Decisions (owner)

**D1. The four skill files.** GOVERNANCE.md §B: skills are "immutable once certified;
enhancements require version bumping, not retroactive editing." So a silent edit is not an option.

- **(a) Retire them (recommended).** Move `.agents/skills/` to `docs/archive/agents_skills_2026-04/`
  with a short README, and amend GOVERNANCE §B to say skills were retired on this date and their
  rules now live in GOVERNANCE.md / CLAUDE.md. Why: no tool or code reads them, and their valid
  rules (no subprocess, append-only triggers, the `grc-faiss` volume is never deleted) are already
  in GOVERNANCE and CLAUDE. Keeping a second, stale copy is what drifted.
- **(b) Version-bump.** Add `SKILL.v2.md` beside each, with SQLite → PostgreSQL and current paths.
  This keeps the pattern, at the cost of four more files to keep in sync.

**D2. Where the Mufasa script goes:** (a) into the Mufasa project folder (Efosa places it; I don't
write into another project unasked), or (b) the GRC Inspector workspace `_archive/` (recommended
if unsure, since it's reversible).

**D3. `run_dashboard.bat`:** fix (B6, recommended: one line) or remove (the Docker stack serves
the UI on `:3006`; the `.bat` starts a separate dev server).

---

## Verification

| Check | Expected |
| --- | --- |
| `git grep -nE "ingest_documents\|DATABASE_PATH\|18,337\|v1\.2\.0"` (code, README, CLAUDE) | no hits outside history docs |
| Rebuild backend (~20 s warm); readiness | 4/4 |
| `docker exec grc-backend ls /app/trigger_ingest.py /app/debug_imports.py` | both absent |
| `pytest` (all but `test_interview_sim.py`, pending a Groq day anyway) | 76 passed, 1 skipped (unchanged) |
| `scripts\run_dashboard.bat` (if fixed) | reaches `npm run dev` from the repo root |
| `faiss_index/` | gone from the repo folder; present in the workspace `_archive/` |

No Groq tokens and no re-ingest.

## Rollback

`git revert` plus a rebuild. D1–D2 moves are moves, not deletions.
