# TPRM Tier 4: Test-Data Hygiene — Reset + Dedicated Test Stack

**Status:** ✅ EXECUTED (2026-08-13). Part (a): dev stack reset twice (once for the initial clean
slate, once more after verifying it left one throwaway `SmokeTest Vendor` behind — see below), final
state confirmed 0 vendors/0 integrations/0 risk-acceptances, FAISS untouched both times. Part (b):
`docker-compose.test.yml` built and running under its own `grc-test` project (fixed a real project-
name collision found during setup — see below), all 8 mutating test files' defaults flipped to
:8002. **Found and fixed two real bugs during verification, not caught in drafting:**
1. Three `docker exec` immutability probes in `test_tprm.py` and four more in `smoke_test.py` (plus
   an autouse fixture in `conftest.py` that runs on *every* test) hardcoded `grc-db-pg`/`grc_audit`
   directly, bypassing the new `GRC_TEST_BASE` switch entirely — meaning every pytest run was still
   writing to the dev stack's `users` table twice per test even after the HTTP-layer fix. Fixed all
   three files to derive `DB_CONTAINER`/`DB_NAME` from the same `GRC_TEST_BASE` value.
2. `docker-compose.test.yml` initially had no explicit `name:`, so Compose inferred the same project
   as the dev stack and flagged its containers as "orphans" of the test project — a real risk had
   `--remove-orphans` ever been used. Fixed with an explicit `name: grc-test`.

Verified: pytest 32/32 and smoke_test.py 43/43 against the test stack (both immutability probes now
pass for real, not vacuously against an empty dev table), dev-stack vendor count confirmed at 0
throughout both runs. One tooling gotcha found along the way, now in `MEMORY.md`: piping
`smoke_test.py` through `head`/`tail` on this Windows/Git-Bash setup silently truncates output via
`BrokenPipeError` while still reporting exit code 0 (the pipe's last command's code, not the
script's) — direct file redirection is required instead.
**Found/scoped:** 2026-08-13. Confirmed via live DB inspection (not assumed from the week-old
"435 vendors" figure): current counts are 608 vendors / 607 integrations / 7,853 stage responses /
126 risk acceptances / 24 evidence links / 810 audit logs / 2,109 security events, still climbing.
**Confirmed 100% of it is test-generated** — every vendor name matches a known test pattern
(`pytest-vendor-*` ×575, `SmokeTest Vendor *` ×25, plus 8 one-off verification-script vendors).
**Confirmed why a cleanup script can't work:** `risk_acceptances`/`evidence_chain`/
`stage_evidence_links` block DELETE, UPDATE, *and* TRUNCATE (`pg_trigger`, not just
`information_schema.triggers` — checked both), and every FK from `integrations`/`vendors` down to
those tables is `NO ACTION` (no cascade). Any integration/vendor that ever had a risk acceptance
signed is permanently undeletable short of disabling the immutability trigger — not something to do
quietly, since it's the literal subject of the Mufasa interview story.

## Two parts, both approved by the user together

### Part (a): Reset the current dataset

Since 100% of current data is confirmed test noise (zero real usage has happened yet — this will be
the *first* real data this app ever holds, via the upcoming dogfooding pass), the clean fix is a
targeted volume reset, not a row-by-row cleanup.

**Only these two volumes get removed:**
- `grc_command_center_grc-db-data` (Postgres data — everything above lives here)
- `grc_command_center_grc-tprm-evidence` (uploaded evidence files — orphaned once their DB rows
  are gone anyway)

**Explicitly NOT touched:**
- `grc_command_center_grc-faiss` (FAISS index — 158 PDFs, ~11 min to rebuild, has nothing to do
  with TPRM data and would be pure collateral damage from a blanket `down -v`)
- `grc_command_center_grc-db-backups` (automated backups, 30-day retention, no reason to touch)
- `grc_command_center_grc-db` (an orphaned volume not referenced anywhere in the current compose
  file — noticed in passing, out of scope, not touched)

**Commands:**
```powershell
docker compose -f docker-compose-v2.yml down          # stop containers, keep all volumes
docker volume rm grc_command_center_grc-db-data grc_command_center_grc-tprm-evidence
docker compose -f docker-compose-v2.yml up -d          # recreate; lifespan re-seeds admin/analyst/
                                                         # viewer users, 5 policies, 26 TPRM
                                                         # reference stages automatically
```

**Verify:** readiness green, FAISS still "Verified OK" (untouched, no re-ingest), 0 vendors/0
integrations, users/policies/TPRM-stages present, one clean smoke-test pass to confirm the reset
stack still works end to end.

### Part (b): Dedicated test stack, so this doesn't reaccumulate

New file `docker-compose.test.yml` — an isolated `db-test` + `backend-test` pair, own ports, own
volumes, so `smoke_test.py`/`pytest` never touch the dev/dogfooding database again:

```yaml
services:
  db-test:
    image: postgres:16-alpine
    container_name: grc-db-pg-test
    environment:
      POSTGRES_DB: grc_audit_test
      POSTGRES_USER: ${POSTGRES_USER:-grc_admin}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-grc_password_2026}
    volumes:
      - grc-db-data-test:/var/lib/postgresql/data
    networks: [grc-net-test]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-grc_admin} -d grc_audit_test"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend-test:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: grc-backend-test
    depends_on:
      db-test:
        condition: service_healthy
    ports:
      - "8002:8001"
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-grc_admin}:${POSTGRES_PASSWORD:-grc_password_2026}@db-test:5432/grc_audit_test
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - DOCUMENTS_PATH=/app/GRC_Analyst
      - AUTH_ENABLED=true
    volumes:
      - grc-faiss:/app/faiss_index:ro        # reuses the REAL index, read-only -- avoids an
                                              # unnecessary 11-min re-ingest; nothing in the test
                                              # suite calls POST /ingest, so read-only is safe
      - grc-tprm-evidence-test:/app/data/tprm_evidence
    networks: [grc-net-test]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/v1/health')"]
      interval: 30s
      timeout: 30s
      retries: 5
      start_period: 60s

volumes:
  grc-db-data-test:
    driver: local
  grc-tprm-evidence-test:
    driver: local
  grc-faiss:
    external: true
    name: grc_command_center_grc-faiss

networks:
  grc-net-test:
    driver: bridge
```

**Test-file changes** — every file that currently hardcodes `localhost:8001` and *mutates state*
(creates vendors/users/etc.) gets the same one-line pattern already used nowhere yet in this repo,
consistently applied, default flipped to the new test stack:

| File | Change |
|---|---|
| `smoke_test.py` | `BASE = "http://localhost:8001"` → `BASE = os.environ.get("GRC_TEST_BASE", "http://localhost:8002")` |
| `test_auth.py` | same pattern |
| `test_tprm.py` | already has the env-var pattern — just flip the default `8001` → `8002` |
| `test_iam_05/07/08/09/10.py` | `BASE_URL = "http://localhost:8001/api/v1"` → `BASE_URL = os.environ.get("GRC_TEST_BASE", "http://localhost:8002") + "/api/v1"` |

**Explicitly NOT changed:** `rag_benchmark.py`, `diagnose_rag.py`, `validate_diagnostic.py` — these
are read-only against `/chat`, never create TPRM data, aren't part of this problem. Left pointed at
the real stack (`localhost:8001`) by default, unchanged.

**Default flip means:** running `pytest` or `python backend/tests/smoke_test.py` with no env var now
hits the isolated test stack automatically — the safe-by-default behavior this item exists to
create. Checking the *real* dev/dogfooding stack's health going forward means either hitting
`/api/v1/readiness` directly (already stack-agnostic, no writes) or explicitly setting
`GRC_TEST_BASE=http://localhost:8001` to point the suite at it on purpose.

**MEMORY.md's "boot & verify" ritual gets updated** to reflect this — the mutating smoke/pytest
suites now run against the disposable test stack by default; the dev stack itself is confirmed
healthy via readiness + light read-only spot checks, not the full mutating suite.

**One-time cost:** first boot of `backend-test` needs one `POST /ingest`-equivalent — actually
none needed, since it mounts the real `grc-faiss` volume read-only and never ingests itself. No
11-minute wait. `db-test` starts empty (no vendors/integrations) and re-seeds users/policies/TPRM
stages via the same `lifespan` startup logic as the real stack.

## Verification plan

- Part (a): readiness green, FAISS untouched (verify hash check still passes, no re-ingest
  triggered), fresh smoke-test pass against the reset dev stack (expect the same 43/43, now with
  clean low vendor/integration counts).
- Part (b): boot `docker-compose.test.yml`, confirm `grc-backend-test` reaches healthy without
  triggering ingestion, run `pytest` and `smoke_test.py` with no env var set and confirm they hit
  port 8002 (not 8001) — check via `docker exec grc-db-pg-test psql ... 'select count(*) from
  vendors'` growing, and confirm the *real* `grc-db-pg`'s vendor count stays at 0 (or whatever the
  dogfooding pass has put there by then) throughout the run.
