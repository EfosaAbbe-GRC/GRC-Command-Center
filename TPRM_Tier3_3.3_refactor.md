# TPRM Tier 3 · Item 3.3 — Draft Diff (per GOVERNANCE.md draft-first protocol)

**Status:** ✅ EXECUTED (2026-08-04). Applied per the confirmed "full upload" architecture (design
call for fetch-on-expand vs. explicit-click resolved as fetch-on-expand, per my recommendation).
**Real infra bug found and fixed mid-execution, beyond what the draft anticipated:** the new
`grc-tprm-evidence` Docker volume mounted as root-owned on first creation (since
`data/tprm_evidence` didn't pre-exist in the image at a path the Dockerfile already `chown`s,
unlike `faiss_index` which does), so every upload 500'd with `[Errno 13] Permission denied` under
the non-root `grcuser` the container runs as. Fixed by adding `data/tprm_evidence` to
`Dockerfile.backend`'s existing `mkdir -p ... && chown -R grcuser:grcuser /app` line (matching the
already-proven `faiss_index` pattern exactly), then removing and letting Docker recreate the
already-broken (confirmed empty) volume so it correctly inherited ownership from the fixed image.
**Verified end-to-end:** smoke 42/42 (twice, before and after the durability check), pytest 32/32
solo (26 prior + 4 new + 2 CSV-export from 3.2 already counted — includes an upload/readback round
trip, an RBAC 403, an empty-file 422, and a direct-SQL immutability probe), plus a manual durability
proof — uploaded a real file, ran a normal `docker compose up -d --build` (no volume removal this
time), and confirmed both the file on disk and its `evidence_chain`/`stage_evidence_links` rows
were still present and correctly linked afterward. One transient false alarm along the way: a full
`docker compose down` + `up` cycle produced a storm of spurious 401s/connection resets in one
smoke+pytest pair, traced to post-teardown network turbulence (not a code regression) — a clean
solo re-run came back green, confirmed by the later durability-check rebuild also passing cleanly.
Not browser-verified (no browser tool this session, consistent gap across 2.3/3.1/3.2/3.3).
**Scope:** `TPRM_Roadmap.md` §3.3, the last Tier 3 item — let a stage attach real evidence
(hashed, chain-of-custody file) into the existing immutable `evidence_chain`, reusing
`AuditLogger.log_evidence`, instead of free-text `evidence_notes` only. Files touched:
`backend/core/database.py`, `backend/core/tprm.py`, `docker-compose-v2.yml`, `src/lib/api.js`,
`src/terminals/VendorRiskTerminal.jsx`, `backend/tests/test_tprm.py`.

**What I found in the current code (context for the design below):**
- This codebase has **no file-upload endpoint anywhere** — no `UploadFile`/`File(...)` in any
  route. `python-multipart` is already a declared dependency (FastAPI needs it for multipart
  parsing), so no new package is required.
- `AuditLogger.log_evidence` / `_log_evidence_async` (`database.py`) is called from exactly one
  place today — `rag.py`'s ingestion loop, already wrapped in its own `try/except`. The function
  currently **returns nothing** and **swallows its own exceptions internally** (logs to stdout
  only). Neither is usable as-is for TPRM: I need the resulting `evidence_chain.id` back to link a
  stage to it, and a silent swallow would make a failed upload look like it succeeded.
- **Real durability gap found:** `docker-compose-v2.yml`'s `backend` service has no volume mount
  for `backend/data/` — only `grc-faiss` and the read-only corpus are mounted. Writing uploaded
  evidence under `data/tprm_evidence/` without a new named volume would mean **every rebuild
  silently deletes all uploaded evidence files** while their `evidence_chain` rows (in the durable
  Postgres volume) keep pointing at now-missing paths. Adding a new `grc-tprm-evidence` volume,
  mirroring the existing `grc-faiss` pattern, is necessary for this feature to actually be durable
  — not optional, so folding it into this item rather than treating it as a separate ask.

**Design:**
1. **`log_evidence` becomes return-value-bearing and exception-propagating.** Dedup-hit path
   returns the *existing* row's id (so re-uploading identical evidence still links correctly,
   rather than silently linking nothing); the internal `try/except` is removed since the one real
   caller (`rag.py`) already wraps its own call and will now correctly report a failure instead of
   silently treating a broken evidence-log as a successful ingest.
2. **New append-only `StageEvidenceLink` table** (own file, `core/tprm.py`) rather than adding
   TPRM-specific columns to the shared `EvidenceChain` model — keeps the flagship RAG evidence
   table untouched, matches how `RiskAcceptance` already links to a stage. Given `BEFORE
   UPDATE/DELETE/TRUNCATE` immutability, folded into `database.py::init_db()`'s existing trigger
   block, same as `risk_acceptances`/`audit_logs`/`evidence_chain`.
3. **Server-generated disk filenames only** (`uuid4().hex`, no extension, no client-filename
   component) — the original filename is preserved purely as `EvidenceChain.filename` metadata,
   never used to construct a filesystem path, closing off path-traversal risk entirely.
4. **25MB upload cap**, rejecting oversized or empty files before writing anything to disk.
5. **Not building:** a raw-file download/re-serve endpoint. Scope is "attach + hash + metadata
   readback," consistent with how `evidence_chain` entries from RAG ingestion also aren't
   independently downloadable through the API today — say so if you want that added too.

---

## 1. `backend/core/database.py`

**`_log_evidence_async`** — return the row id (new vs. existing-dedup), let exceptions propagate:
```python
    async def _log_evidence_async(self, filename: str, file_hash: str, file_size: int, source_path: str, ingested_by: str = "system") -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(EvidenceChain).where(
                    EvidenceChain.filename == filename,
                    EvidenceChain.file_hash == file_hash,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                logger.info("Evidence: File already recorded", filename=filename, hash=file_hash[:16])
                return existing.id

            entry = EvidenceChain(
                filename=filename,
                file_hash=file_hash,
                file_size_bytes=file_size,
                source_path=source_path,
                ingested_by=ingested_by,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
        logger.info("Evidence: Chain-of-custody recorded", filename=filename, hash=file_hash[:16])
        return entry.id

    def log_evidence(self, filename: str, file_hash: str, file_size: int, source_path: str, ingested_by: str = "system") -> int:
        """Sync bridge: called from RAG ingestion loop and TPRM stage evidence upload."""
        return _run_async(self._log_evidence_async(filename, file_hash, file_size, source_path, ingested_by))
```
(removed the outer `try/except Exception as e: logger.error(...)` — `rag.py`'s call site already
has its own `try/except` around this call, so failures now correctly surface as a per-file
ingestion error instead of a silent no-op.)

**`init_db()`** — new trigger block for `stage_evidence_links`, alongside the existing
`risk_acceptances` block:
```python
                # 5. Stage evidence links (TPRM) — block UPDATE and DELETE/TRUNCATE.
                # Reuses fn_prevent_immutability_violation(); guarded so it is a
                # no-op until the TPRM models have been registered/created.
                await conn.execute(text("""
                    DO $$ BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'stage_evidence_links') THEN
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_stage_evidence_no_update') THEN
                                CREATE TRIGGER trg_stage_evidence_no_update BEFORE UPDATE ON stage_evidence_links
                                FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_stage_evidence_no_delete') THEN
                                CREATE TRIGGER trg_stage_evidence_no_delete BEFORE DELETE ON stage_evidence_links
                                FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_stage_evidence_no_truncate') THEN
                                CREATE TRIGGER trg_stage_evidence_no_truncate BEFORE TRUNCATE ON stage_evidence_links
                                FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                        END IF;
                    END $$;
                """))
```
(exact guard style copied from the existing `risk_acceptances` block — table-existence-gated so
it's a no-op before `tprm.py`'s models are registered on first boot, then self-heals on next boot.)

---

## 2. `backend/core/tprm.py`

**New imports:**
```python
import hashlib
import os
from fastapi import UploadFile, File
from core.database import audit_logger
from core.models import EvidenceChain
```

**New constants**, near the top:
```python
MAX_EVIDENCE_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB
TPRM_EVIDENCE_DIR = os.path.join("data", "tprm_evidence")
os.makedirs(TPRM_EVIDENCE_DIR, exist_ok=True)
```

**New model**, alongside `RiskAcceptance`:
```python
class StageEvidenceLink(Base):
    """Append-only. init_db() installs UPDATE/DELETE/TRUNCATE-blocking triggers."""
    __tablename__ = "stage_evidence_links"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("assessment_stages.id"), nullable=False)
    evidence_chain_id = Column(Integer, ForeignKey("evidence_chain.id"), nullable=False)
    linked_by = Column(String(255), nullable=False)
    linked_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
```

**New upload route**, placed after `submit_stage_response`:
```python
@router.post(
    "/integrations/{integration_id}/stages/{stage_id}/evidence",
    dependencies=[Depends(authorize(CAP_ASSESS))],
)
async def upload_stage_evidence(
    integration_id: uuid.UUID,
    stage_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user(request)
    result = await db.execute(
        select(StageResponse).where(
            StageResponse.integration_id == integration_id,
            StageResponse.stage_id == stage_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Stage response not found for this integration")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=422, detail="Empty file")
    if len(contents) > MAX_EVIDENCE_UPLOAD_BYTES:
        raise HTTPException(status_code=413,
            detail=f"File exceeds {MAX_EVIDENCE_UPLOAD_BYTES // (1024*1024)}MB limit")

    file_hash = hashlib.sha256(contents).hexdigest()
    disk_path = os.path.join(TPRM_EVIDENCE_DIR, uuid.uuid4().hex)  # server-generated name only
    with open(disk_path, "wb") as fh:
        fh.write(contents)

    evidence_id = audit_logger.log_evidence(
        filename=file.filename or "unnamed",
        file_hash=file_hash,
        file_size=len(contents),
        source_path=disk_path,
        ingested_by=current_user["username"],
    )

    link = StageEvidenceLink(
        integration_id=integration_id, stage_id=stage_id,
        evidence_chain_id=evidence_id, linked_by=current_user["username"],
    )
    db.add(link)
    await db.commit()

    log_security_event(request, "TPRM_EVIDENCE_LINKED",
        f"Evidence '{file.filename}' (sha256:{file_hash[:16]}...) linked to stage {stage_id} "
        f"on integration {integration_id} by {current_user['username']}")
    return {"status": "evidence linked", "evidence_chain_id": evidence_id, "file_hash": file_hash}
```

**New read-back route**, right after it:
```python
@router.get(
    "/integrations/{integration_id}/stages/{stage_id}/evidence",
    dependencies=[Depends(authorize(CAP_VIEW))],
)
async def list_stage_evidence(integration_id: uuid.UUID, stage_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StageEvidenceLink, EvidenceChain)
        .join(EvidenceChain, EvidenceChain.id == StageEvidenceLink.evidence_chain_id)
        .where(
            StageEvidenceLink.integration_id == integration_id,
            StageEvidenceLink.stage_id == stage_id,
        )
        .order_by(StageEvidenceLink.linked_at.desc())
    )
    return [
        {
            "link_id": str(link.id), "evidence_chain_id": ev.id, "filename": ev.filename,
            "file_hash": ev.file_hash, "file_size_bytes": ev.file_size_bytes,
            "linked_by": link.linked_by, "linked_at": link.linked_at,
        }
        for link, ev in result.all()
    ]
```

No changes needed to the CSV export (3.2) or the RBAC seed list — reuses `CAP_ASSESS`/`CAP_VIEW`,
already seeded.

---

## 3. `docker-compose-v2.yml`

**New named volume** for the backend service:
```yaml
    volumes:
      - grc-faiss:/app/faiss_index
      - grc-tprm-evidence:/app/data/tprm_evidence
      - "${DOCUMENTS_PATH}:/app/GRC_Analyst:ro"
```
**Declare it** in the top-level `volumes:` block, alongside `grc-faiss`:
```yaml
  grc-tprm-evidence:
    driver: local
```

---

## 4. `src/lib/api.js`

**New upload helper**, alongside `downloadFile`:
```javascript
    uploadFile: async (endpoint, file) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}${endpoint}`, {
            method: 'POST',
            headers: { ...getAuthHeaders() },  // no Content-Type — browser sets the multipart boundary
            body: formData,
        });
        if (!response.ok) {
            let errorData = {};
            try { errorData = await response.json(); } catch { /* ignore parse error */ }
            throw new Error(errorData.detail || `Upload failed (${response.status})`);
        }
        return await response.json();
    },
```

---

## 5. `src/terminals/VendorRiskTerminal.jsx`

Inside the existing stage-detail expandable panel (from 2.1), add an Evidence section: list
already-linked evidence (filename, hash prefix, size, linked by/at) plus a file input for
`canAssess` users. Fetch-on-expand (only when a stage row is opened, not eagerly for all 13 stages
— avoids 13x extra requests per integration open) via a small `loadEvidence(stageId)` helper wired
to the existing `expandedStage` toggle, storing results in a `{ [stageId]: [...] }` map state.

Exact JSX/state wiring will follow the same expand-panel pattern already in this file (2.1's
`StageDetailField`); I'll write the precise diff during implementation rather than pre-committing
it line-for-line here, since it depends on where `setExpandedStage` is called and I want to re-read
the current stage-row block fresh (it's shifted since 2.1's original draft, having gained N/A
buttons from 2.4 and risk-acceptance UI from 2.2).

---

## 6. `backend/tests/test_tprm.py`

New tests: `test_tprm_evidence_upload_and_readback` (upload a small in-memory file, assert 200 +
hash matches, then GET the stage evidence list and confirm the linked entry appears with matching
hash/filename), `test_tprm_evidence_upload_requires_assess` (viewer → 403), `test_tprm_evidence_
upload_rejects_empty_file` (422), `test_tprm_evidence_link_immutable` (mirrors the existing
`test_tprm_risk_acceptance_truncate_blocked` pattern — direct-SQL UPDATE/DELETE against
`stage_evidence_links` blocked by the trigger).

---

## Verification plan

Real schema change this time (new table + new triggers) — will rebuild both containers, run smoke
+ pytest, and manually verify: upload via curl, confirm the file lands in the new volume-backed
directory (`docker exec grc-backend ls data/tprm_evidence/`), confirm the trigger blocks a direct
UPDATE via `docker exec ... psql`, and confirm the volume survives a rebuild (upload, rebuild,
re-check the file and its DB row are both still present) — this last check is the one that
actually proves the durability-gap finding is fixed, not just theoretically addressed.

## Confirm before I execute

Everything above reflects the confirmed "full upload" architecture. Flagging one more open call:
should the evidence section auto-fetch when a stage row expands (my default plan above), or only
on an explicit "show evidence" click within the expanded panel — the former is more useful
day-to-day, the latter is marginally more conservative on request volume (13 stages × however many
already have evidence, only on-demand per row, not per-integration-open, so this is a small
consideration either way).

Reply **EXECUTE** (with any adjustments) and I'll apply, rebuild, and verify.
