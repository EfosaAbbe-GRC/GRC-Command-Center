# TPRM Tier 3 · Item 3.2 — Draft Diff (per GOVERNANCE.md draft-first protocol)

**Status:** ✅ EXECUTED (2026-08-03). Applied exactly as drafted. Verified: smoke 42/42, pytest
28/28 (26 + 2 new: `test_tprm_export_csv`, `test_tprm_export_csv_requires_evidence_export_capability`).
Manual `curl` check confirmed correct `Content-Disposition`/`Content-Type` headers, real data across
all three `--- SECTION ---` markers (271+ integrations from accumulated test data — see Tier 4.2
test-data-hygiene backlog item, unrelated to this change), and RBAC enforcement (analyst → 403,
admin → 200). Not browser-verified (no browser tool this session, same gap as 2.3/3.1) — the curl
check substitutes for confirming the download itself, though the `api.downloadFile()` blob/anchor
mechanism specifically wasn't exercised in a real browser.
**Scope:** `TPRM_Roadmap.md` §3.2 — CSV export of the full TPRM assessment register (auditor-facing
evidence, parity with `/compliance/export`; decision #3 already locked CSV-first, PDF later). Files
touched: `backend/core/tprm.py`, `src/lib/api.js`, `src/terminals/ComplianceTerminal.jsx`,
`src/terminals/VendorRiskTerminal.jsx`.

**What I found in the current code (context for the design below):**
- `main.py`'s `export_compliance_csv` (`GET /compliance/export`) is the mirror target: a plain
  `StreamingResponse` of an `io.StringIO()` CSV buffer, gated by an existing `EVIDENCE_EXPORT`
  capability (admin, "Export and download compliance audit evidence" — already seeded, not TPRM-
  specific). Confirmed with you to reuse this capability rather than add a fourth TPRM-only one.
- **Second real pre-existing bug found, confirmed with you to fix alongside this:**
  `ComplianceTerminal.jsx`'s "Export CSV Report" button triggers the download via
  `window.location.href = url` — but `/compliance/export` is not in `auth.py`'s `PUBLIC_ROUTES`,
  and `AuthMiddleware` requires the `Authorization` header on every protected route with **no**
  cookie or query-param fallback for plain HTTP requests (only the WebSocket endpoint has a
  `?token=` fallback). A bare browser navigation sends no such header, so this button currently
  401s instead of downloading. Same family of bug as `OpsTerminal.jsx`'s dead WebSocket from 3.1 —
  a frontend action that bypasses `api.js`'s auth-header plumbing. Fixing it via a shared
  `api.downloadFile()` helper (authenticated fetch → blob → client-side download) that both the
  fixed `ComplianceTerminal.jsx` button and the new TPRM export button will use.
- `api.js`'s `fetchWithRetry` always calls `response.json()` — can't be reused as-is for a CSV
  response, hence the new dedicated helper rather than routing through `api.get`.

**Design:**
1. **CSV shape** — three sections, mirroring `/compliance/export`'s "main table + `---
   SECTION ---` + sub-table" layout, extended to three because TPRM has three levels of evidence:
   (a) Integrations (vendor, name, direction, method, risk tier, status, reassessment due),
   (b) Stage Assessments (one row per stage response — the actual 13-stage evidence),
   (c) Risk Acceptances (the append-only exception trail). This is the full "defensible artifact"
   the roadmap calls for — an auditor can reconstruct the whole assessment state from one file.
2. **Capability** — reuse `EVIDENCE_EXPORT` (confirmed above).
3. **Frontend button placement** — `VendorRiskTerminal.jsx` header, gated by the existing
   `canSignoff` (role === 'admin') variable, matching `EVIDENCE_EXPORT`'s admin seed level.

---

## 1. `backend/core/tprm.py`

**New imports** (top of file):
```python
import csv
import io
from fastapi.responses import StreamingResponse
```

**New route**, placed after `get_expiring_acceptances`:
```python
@router.get("/export", dependencies=[Depends(authorize("EVIDENCE_EXPORT"))])
async def export_tprm_csv(db: AsyncSession = Depends(get_db)):
    """Streaming CSV export of the full TPRM assessment register: integrations,
    stage-level assessment detail, and risk acceptances. Mirrors main.py's
    export_compliance_csv (multi-section CSV, StreamingResponse)."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["--- INTEGRATIONS ---"])
    writer.writerow(["Vendor", "Integration", "Direction", "Transfer Method", "Risk Tier",
                      "Status", "Reassessment Due", "Created By", "Created At"])
    result = await db.execute(
        select(Integration, Vendor.name)
        .join(Vendor, Vendor.id == Integration.vendor_id)
        .order_by(Vendor.name, Integration.name)
    )
    for integration, vendor_name in result.all():
        writer.writerow([
            vendor_name, integration.name, integration.direction.value,
            integration.transfer_method.value, integration.computed_risk_tier.value,
            integration.status.value,
            integration.reassessment_due.isoformat() if integration.reassessment_due else "",
            integration.created_by, integration.created_at.isoformat(),
        ])

    writer.writerow([])
    writer.writerow(["--- STAGE ASSESSMENTS ---"])
    writer.writerow(["Vendor", "Integration", "Stage #", "Stage Title", "Status",
                      "Evidence Notes", "Reviewed By", "Reviewed At"])
    result = await db.execute(
        select(Vendor.name, Integration.name, AssessmentStage.stage_number,
               AssessmentStage.title, StageResponse.status, StageResponse.evidence_notes,
               StageResponse.reviewed_by, StageResponse.reviewed_at)
        .select_from(StageResponse)
        .join(Integration, Integration.id == StageResponse.integration_id)
        .join(Vendor, Vendor.id == Integration.vendor_id)
        .join(AssessmentStage, AssessmentStage.id == StageResponse.stage_id)
        .order_by(Vendor.name, Integration.name, AssessmentStage.stage_number)
    )
    for vendor_name, integ_name, stage_num, title, status, notes, reviewer, reviewed_at in result.all():
        writer.writerow([
            vendor_name, integ_name, stage_num, title, status.value, notes or "",
            reviewer or "", reviewed_at.isoformat() if reviewed_at else "",
        ])

    writer.writerow([])
    writer.writerow(["--- RISK ACCEPTANCES ---"])
    writer.writerow(["Vendor", "Integration", "Stage #", "Stage Title", "Gap Description",
                      "Compensating Control", "Accepted By", "Accepted At", "Expires At"])
    result = await db.execute(
        select(Vendor.name, Integration.name, AssessmentStage.stage_number, AssessmentStage.title,
               RiskAcceptance.gap_description, RiskAcceptance.compensating_control,
               RiskAcceptance.accepted_by, RiskAcceptance.accepted_at, RiskAcceptance.expires_at)
        .select_from(RiskAcceptance)
        .join(Integration, Integration.id == RiskAcceptance.integration_id)
        .join(Vendor, Vendor.id == Integration.vendor_id)
        .join(AssessmentStage, AssessmentStage.id == RiskAcceptance.stage_id)
        .order_by(Vendor.name, Integration.name, RiskAcceptance.accepted_at)
    )
    for vendor_name, integ_name, stage_num, title, gap, control, accepted_by, accepted_at, expires_at in result.all():
        writer.writerow([
            vendor_name, integ_name, stage_num, title, gap, control, accepted_by,
            accepted_at.isoformat(), expires_at.isoformat(),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tprm_assessment_report.csv"},
    )
```

No schema/migration risk — read-only, no new columns.

---

## 2. `src/lib/api.js`

**New shared download helper**, alongside the other `api` methods:
```javascript
    downloadFile: async (endpoint, filename) => {
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}${endpoint}`, {
            headers: { ...getAuthHeaders() }
        });
        if (!response.ok) {
            throw new Error(`Download failed (${response.status})`);
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    },
```

---

## 3. `src/terminals/ComplianceTerminal.jsx` (bug fix, confirmed in scope)

**Replace the broken download trigger:**
```jsx
                    {isAdmin && (
                        <button
                            onClick={() => api.downloadFile('/compliance/export', 'grc_compliance_report.csv')}
                            className="flex items-center gap-2.5 px-6 py-2 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] text-white rounded-md font-bold transition-all shadow-[0_0_15px_var(--accent-glow)] active:scale-95 group relative overflow-hidden"
                        >
```
(was the `window.location.href = ...` handler). `api` is already imported in this file.

---

## 4. `src/terminals/VendorRiskTerminal.jsx`

**New "Export CSV" button**, in the header next to the reassessment badge, gated by `canSignoff`
(admin — matches `EVIDENCE_EXPORT`'s seed level):
```jsx
            {canSignoff && (
              <button
                onClick={() => api.downloadFile('/tprm/export', 'tprm_assessment_report.csv')}
                className="p-1.5 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] rounded transition"
                title="Export TPRM Assessment Report (CSV)"
              >
                <Download size={14} />
              </button>
            )}
```
(new `Download` icon import, added to the existing lucide-react import line.)

---

## Verification plan

No schema/migration risk. Will rebuild both containers, run smoke + pytest, add a
`test_tprm_export_csv` (asserts 200, `text/csv` content-type, and that all three `--- SECTION ---`
markers are present in the body — plus an RBAC check that analyst gets 403), and a manual
`curl`-based download to confirm the CSV actually parses and contains real data (same substitute
used throughout this session, no browser tool available).
