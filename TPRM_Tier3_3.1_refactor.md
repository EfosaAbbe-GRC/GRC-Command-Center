# TPRM Tier 3 · Item 3.1 — Draft Diff (per GOVERNANCE.md draft-first protocol)

**Status:** ✅ EXECUTED (2026-08-03). Applied exactly as drafted. Verified: smoke 42/42, pytest
26/26 (no regression from the 4 new broadcast call sites). No automated test for the WS broadcast
itself — `websockets` is only a transitive uvicorn dependency (not declared, not used anywhere in
this sync/`requests`-based test suite), so adding an async WS test would have been a bigger
paradigm shift than this item warranted. Used the pre-committed fallback instead: a one-off script
(`verify_ws_broadcast.py`, not part of the permanent suite) opened a real WS connection, triggered
`create_integration`, and confirmed a `{"type": "TPRM_REASSESSMENT_STATUS"}` frame arrived within
10s — **PASS**. Also confirmed `/tprm/reassessments/due` and `/tprm/acceptances/expiring` still
return correct (currently empty — nothing in this environment is naturally overdue/expired yet)
data. **Not browser-verified** — no browser-automation tool this session (same gap as 2.3), and
additionally there's currently no naturally-overdue data to visually confirm the badge's conditional
render against even if a browser tool were available.
**Scope:** `TPRM_Roadmap.md` §3.1 — surface `GET /reassessments/due` and `GET /acceptances/expiring`
(both exist, both unconsumed) via a dashboard badge/panel, pushed over the WebSocket event bus
instead of `setInterval` (GOVERNANCE §3 polling ban). Files touched: `backend/core/tprm.py`,
`src/lib/api.js`, `src/terminals/VendorRiskTerminal.jsx`, `src/terminals/OpsTerminal.jsx`.

**What I found in the current code (context for the design below):**
- `core/ws.py`'s `ConnectionManager.broadcast` has exactly one existing call site
  (`main.py`'s `trigger_ingest`, fires `INGEST_STATUS` once on the ingest-trigger action). There is
  **no scheduler/periodic-task infrastructure anywhere in this codebase.**
- There is **no "mark reassessed" / renew endpoint at all** — once `reassessment_due` passes, or a
  risk acceptance expires, nothing in the API can clear it. Out of scope for 3.1 (which is about
  surfacing existing data, not adding a renew workflow) — flagging so the badge's one-directional
  behavior isn't mistaken for a bug later.
- **Real bug found, confirmed with you to fix alongside this:** `OpsTerminal.jsx`'s
  `useWebSocket(user?.access_token, ...)` passes `undefined` — `user` (from `AuthContext.jsx`) is
  `{username, role, mustChangePassword}`, never the raw token. `useWebSocket`'s `connect()` bails
  out on a falsy token, so **Ops Terminal's telemetry stream has never actually connected.** The
  real token lives in `api.js`'s private `tokenStore`, never exported.

**Design (both calls confirmed):**
1. **Event-driven broadcast, no backend timer.** Broadcast a bare `{"type":
   "TPRM_REASSESSMENT_STATUS"}` signal (no payload — the receiving terminal already has the two
   GET routes; it just re-fetches them) whenever a TPRM action could plausibly change the due/
   expiring picture: `create_integration`, `create_risk_acceptance`, both `approve_integration`
   success paths. **Known limitation, accepted:** a due-date or expiry passing purely on the wall
   clock with nobody touching TPRM won't push a live update — the badge refreshes on mount, on
   reconnect, and on the next real action. No new scheduler infrastructure added.
2. **Badge + expandable panel** in `VendorRiskTerminal.jsx`'s own header, plus **fixing the token
   bug** via a new `api.getAccessToken()` (exposes the existing private `tokenStore.getAccess`),
   used correctly in both the new code and as a one-line fix to `OpsTerminal.jsx`.

---

## 1. `backend/core/tprm.py`

**Import the WS manager** (new import, top of file):
```python
from core.ws import manager
```

**Broadcast helper**, placed near the other Tier-3-relevant routes (~after `_recompute_vendor_tier`):
```python
async def _broadcast_reassessment_status() -> None:
    """Nudge connected terminals to re-fetch /reassessments/due and
    /acceptances/expiring. No payload — GOVERNANCE bans setInterval polling
    on the frontend, not a WS-triggered single fetch; keeping the broadcast
    payload-free avoids duplicating those two routes' query logic here."""
    await manager.broadcast({"type": "TPRM_REASSESSMENT_STATUS"})
```

**Call it at four points** (all after the existing commit/refresh, so the broadcast reflects
committed state):
- End of `create_integration`, right after the existing `await _recompute_vendor_tier(...)` call.
- End of `create_risk_acceptance`, right after `log_security_event(...)`, before `return`.
- End of both `approve_integration` success paths (clean-approve and approved-with-exceptions),
  right after their `await _recompute_vendor_tier(...)` calls.

No schema/migration risk — pure application logic, no new columns or enum values.

---

## 2. `src/lib/api.js`

**Expose the access token** (new method on the `api` export, alongside `getUser`):
```javascript
    getAccessToken: () => tokenStore.getAccess(),
```

---

## 3. `src/terminals/OpsTerminal.jsx` (one-line bug fix, confirmed in scope)

**Replace the broken token source:**
```jsx
    const { connected } = useWebSocket(api.getAccessToken(), (message) => {
```
(was `useWebSocket(user?.access_token, ...)`). `api` is already imported in this file.

---

## 4. `src/terminals/VendorRiskTerminal.jsx`

**New imports:**
```jsx
import { Bell } from 'lucide-react';               // added to the existing lucide-react import
import { useWebSocket } from '../hooks/useWebSocket';
```

**New data hooks**, alongside the existing `integrations`/`vendors` ones:
```jsx
  const { data: dueReassessments, refresh: refreshDue } = useApiData('/tprm/reassessments/due');
  const { data: expiringAcceptances, refresh: refreshExpiring } = useApiData('/tprm/acceptances/expiring');
  const [showReassessPanel, setShowReassessPanel] = useState(false);
```

**WebSocket subscription** (new, this component doesn't use `useWebSocket` today):
```jsx
  useWebSocket(api.getAccessToken(), (message) => {
    if (message.type === 'TPRM_REASSESSMENT_STATUS') {
      refreshDue();
      refreshExpiring();
    }
  });
```

**Badge**, in the panel header (next to the existing title, before the `Plus` button):
```jsx
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-[var(--accent)]" />
            <h2 className="text-[11px] font-bold tracking-widest uppercase font-display">Vendor Risk Assessments</h2>
            {(dueReassessments?.length > 0 || expiringAcceptances?.length > 0) && (
              <button
                onClick={() => setShowReassessPanel(v => !v)}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded-sm border text-[9px] font-bold uppercase font-mono"
                style={{ borderColor: 'var(--warning)', color: 'var(--warning)', backgroundColor: 'var(--warning-subtle)' }}
              >
                <Bell size={10} />
                {dueReassessments?.length || 0} overdue · {expiringAcceptances?.length || 0} expiring
              </button>
            )}
          </div>
```

**Expandable panel**, rendered directly below the header `div` (before the vendor-portfolio strip
from 2.3):
```jsx
        {showReassessPanel && (
          <div className="px-3 py-2 border-b border-[var(--border-default)] bg-[var(--layer-0)] text-[11px] space-y-2 max-h-48 overflow-y-auto">
            {dueReassessments?.map((r) => (
              <div key={r.integration_id} className="flex justify-between">
                <span className="text-[var(--text-secondary)] truncate">{r.name}</span>
                <span className="text-[var(--warning)] font-mono">{r.days_overdue}d overdue</span>
              </div>
            ))}
            {expiringAcceptances?.map((a) => (
              <div key={a.acceptance_id} className="flex justify-between">
                <span className="text-[var(--text-secondary)] truncate">{a.integration_name}</span>
                <span className="text-[var(--danger)] font-mono">{a.days_expired}d expired</span>
              </div>
            ))}
          </div>
        )}
```

Not building: a global header/nav-level badge (would touch `App.jsx`/`TerminalSwitcher.jsx` for
marginal benefit — this stays scoped to the TPRM terminal, matching 2.1-2.3's precedent), and a
"mark reassessed" workflow (out of scope, flagged above).

---

## Verification plan

No schema/migration risk. Will rebuild both containers, run smoke + pytest, and add a
`test_tprm_reassessment_broadcast_smoke` — since pytest can't easily assert on a WebSocket message
without a websocket test client, this will be a lighter smoke-style check: open a WS connection
with the `websockets` or `httpx` test client, trigger `create_integration`, and assert a
`TPRM_REASSESSMENT_STATUS` frame arrives. If that proves awkward for this test harness, I'll fall
back to a manual `wscat`/browser-console check instead and say so plainly rather than force a
brittle test. Then a manual API-level check (same substitute used for 2.3, no browser tool this
session) confirming `/tprm/reassessments/due` and `/tprm/acceptances/expiring` still return correct
data untouched by this change.
