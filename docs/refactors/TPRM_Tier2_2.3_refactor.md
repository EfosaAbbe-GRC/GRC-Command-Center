# TPRM Tier 2 · Item 2.3 — Draft Diff (per GOVERNANCE.md draft-first protocol)

**Status:** ✅ EXECUTED (2026-08-03). Applied exactly as drafted (both design calls confirmed:
recompute hooked into both create and approve; portfolio strip added). Verified: smoke 42/42,
pytest 26/26 (25 + new `test_tprm_vendor_rollup`), plus a live API check confirming
`/tprm/vendors` now returns a real tier distribution (6 critical, 2 high, 29 medium, 5 low, 202
still correctly `unscored` — those have no integrations yet) instead of every vendor stuck at
`unscored`. **Not independently browser-verified** — no browser-automation tool available this
session (same gap as 2.2); the API-level check above is the substitute, consistent with how 2.2's
gap was handled before its follow-up browser pass.
**Scope:** `TPRM_Roadmap.md` §2.3 — compute `Vendor.overall_risk_tier` as the max tier across a
vendor's integrations (was hard-stuck at `UNSCORED` — the column and `VendorOut` field already
existed, nothing ever wrote to it). Files touched: `backend/core/tprm.py`,
`src/terminals/VendorRiskTerminal.jsx`, `backend/tests/test_tprm.py`.

**What I found in the current code (context for the design below):**
- `computed_risk_tier` on `Integration` is set exactly once, at creation time
  (`create_integration`, `tprm.py:303-314`) — nothing in `approve_integration` or anywhere else
  ever changes it.
- The frontend has **no vendor list/portfolio view at all** today. `vendors` is fetched
  (`useApiData('/tprm/vendors')`) but used only to populate the `<select>` in the
  create-integration modal — vendor name/tier is never rendered anywhere.

**Design calls (flagging both, cheap to change if you'd rather not):**
1. **Recompute hook points:** the roadmap says "recompute on integration create/approve." Since
   `computed_risk_tier` only ever gets *set* at create time, hooking `approve_integration` too is a
   no-op today — but it's one extra query + conditional update, cheap, and protects against a
   future change (e.g. a reassessment flow) that alters an integration's tier post-creation without
   remembering to also touch the vendor rollup. Adding it to both per the roadmap's wording rather
   than skipping the currently-redundant one.
2. **Frontend scope:** since there's no vendor list view to extend, I'm adding a compact
   **vendor portfolio strip** — a horizontally-scrollable row of vendor name + tier-badge chips
   above the integration list, reusing the existing `TIER_STYLE` map. Not building a full
   vendor-detail page (that's bigger than "S/M" and isn't asked for yet). Also appending the tier
   to each vendor's label in the existing create-integration `<select>` (one-line change, free
   visibility). Say so if you'd rather skip the portfolio strip and keep this backend-only for now.

---

## 1. `backend/core/tprm.py`

**Severity ordering + rollup helper**, placed near `compute_risk_tier` (~line 176):
```python
RISK_TIER_SEVERITY = {
    RiskTier.CRITICAL: 4,
    RiskTier.HIGH: 3,
    RiskTier.MEDIUM: 2,
    RiskTier.LOW: 1,
    RiskTier.UNSCORED: 0,
}


async def _recompute_vendor_tier(vendor_id: uuid.UUID, db: AsyncSession) -> None:
    """Vendor.overall_risk_tier = max(severity) across its integrations."""
    result = await db.execute(
        select(Integration.computed_risk_tier).where(Integration.vendor_id == vendor_id)
    )
    tiers = result.scalars().all()
    new_tier = max(tiers, key=lambda t: RISK_TIER_SEVERITY[t]) if tiers else RiskTier.UNSCORED

    vendor = await db.get(Vendor, vendor_id)
    if vendor and vendor.overall_risk_tier != new_tier:
        vendor.overall_risk_tier = new_tier
        await db.commit()
```

**Call it at the end of `create_integration`** (after the stage-response commit, before `return integration`):
```python
    for stage in stages_result.scalars().all():
        db.add(StageResponse(integration_id=integration.id, stage_id=stage.id))
    await db.commit()

    await _recompute_vendor_tier(integration.vendor_id, db)
    return integration
```

**Call it at the end of `approve_integration`**, on both return paths (clean-approve and
approved-with-exceptions — `computed_risk_tier` doesn't change here today, so this is a defensive
no-op per design call #1, not a functional fix):
```python
    if not gap_stage_ids:
        integration.status = IntegrationStatus.APPROVED
        await db.commit()
        await db.refresh(integration)
        await _recompute_vendor_tier(integration.vendor_id, db)
        log_security_event(request, "TPRM_APPROVE",
            f"Integration {integration.id} ('{integration.name}') approved clean")
        return integration
    ...
    integration.status = IntegrationStatus.APPROVED_WITH_EXCEPTIONS
    await db.commit()
    await db.refresh(integration)
    await _recompute_vendor_tier(integration.vendor_id, db)
    log_security_event(request, "TPRM_APPROVE_WITH_EXCEPTIONS", ...)
```

No schema/migration risk — `overall_risk_tier` and its enum type already exist and are already
populated with a valid default (`UNSCORED`), so this is pure application logic, not a new enum
value like 2.4's gotcha.

---

## 2. `src/terminals/VendorRiskTerminal.jsx`

**Vendor portfolio strip** — insert between the panel header and the integration list (after the
header `div` closing at line 110, before the `flex-1 overflow-y-auto` list container):
```jsx
        {vendors?.length > 0 && (
          <div className="flex gap-1.5 px-3 py-2 border-b border-[var(--border-default)] overflow-x-auto shrink-0">
            {vendors.map((v) => {
              const tier = TIER_STYLE[v.overall_risk_tier] || TIER_STYLE.unscored;
              return (
                <div key={v.id}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-sm border shrink-0"
                  style={{ borderColor: tier.color, backgroundColor: tier.bg }}
                  title={`${v.name} — ${v.overall_risk_tier}`}
                >
                  <span className="text-[10px] font-bold text-[var(--text-primary)] truncate max-w-[100px]">{v.name}</span>
                  <span className="text-[8px] font-bold uppercase font-mono" style={{ color: tier.color }}>
                    {v.overall_risk_tier}
                  </span>
                </div>
              );
            })}
          </div>
        )}
```

**Vendor dropdown in the create-integration modal** — append tier to the label (find the
`<select>` populated from `vendors`, currently `{v.name}` only):
```jsx
                {vendors.map((v) => <option key={v.id} value={v.id}>{v.name} — {v.overall_risk_tier}</option>)}
```

Not building: click-to-filter-by-vendor on the strip, or a dedicated vendor detail page — both are
bigger than this item's scope and not blocking anything else in the roadmap.

---

## Verification plan

No schema/migration risk this time (no new columns, no new enum values, `overall_risk_tier`
already exists and defaults validly) — but I'll still rebuild both containers (frontend + backend
changed) and run smoke + pytest. New test coverage: a `test_tprm_vendor_rollup` case creating one
vendor with a LOW and then a CRITICAL integration, asserting the vendor reads `critical` after the
second create (and stays `critical`, not regressing, if a third LOW integration is added).
Then a manual browser check: confirm the portfolio strip renders real tiers, not just `unscored`,
for at least one vendor with a scored integration.

## Confirm before I execute

1. Both recompute hook points (create **and** approve) per design call #1, even though the approve
   hook is a no-op today — or skip approve and only hook create?
2. The vendor portfolio strip (design call #2) — or keep this backend-only for now and skip the
   frontend entirely?

Reply **EXECUTE** (with any adjustments) and I'll apply, rebuild, and verify.
