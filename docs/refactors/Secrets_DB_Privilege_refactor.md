# Secrets out of OneDrive, least-privilege database roles, tamper-evident audit trail

**Status:** **EXECUTED 2026-10-31** (owner's EXECUTE the same day). Drafted 2026-10-25 and kept
out of the repo until applied, because it described a live, proven weakness; it's published now
that the weakness is closed. **What was actually done, and where it differs from this draft: §11.**

> **Re-check on execution: DevSecOps Phase 0 (`855c79f`, 2026-10-27) landed after this draft.**
> - `_creds.py` already reads `GRC_ENV_FILE` first; §4 builds on that (add the
>   `COMPOSE_ENV_FILES` fallback and the OneDrive refusal). `test_suite_hygiene.py` points
>   `GRC_ENV_FILE` at a missing file and expects "No ADMIN_PASSWORD" in the output: keep that
>   message, or update the test in the same change.
> - New policy tests will judge §5's compose changes: give `db-migrate` the backend's
>   `cap_drop: [ALL]` + `no-new-privileges` + `init: true` (and extend `test_backend_runtime_hardening` to it).
>   `test_secrets_are_required` only checks variable names containing PASSWORD/SECRET/API_KEY/TOKEN,
>   so it would **not** catch a `:-` default on `MIGRATE_DATABASE_URL` (it embeds the owner
>   password): widen the pattern to `DATABASE_URL` first, red, then green.
> - The image is now offline (`HF_HUB_OFFLINE=1`) and hash-locked; `core.migrate` needs no new
>   packages, so `requirements.in` shouldn't change. If it must, recompile (command in its header).

**Principle: shift left, security first** (owner's standing rule, 2026-10-25). Every control below
is built in four steps:

1. **threat first**: what we're defending, against whom;
2. **failing tests first**: tests that prove each weakness *today* are written and run before any
   fix (red), then the fix turns them green;
3. **a fail-closed guard**: the system refuses to run if the weakness ever comes back;
4. **least privilege by default**: each component gets only what it needs.

The DevSecOps pipeline (next draft) then runs these same tests on every push.

**Prompted by:** Susan Shepard, *Build It in a Day, Own It Forever* (Medium, 2026-10-19). Her
question, "who could have changed the numbers?", applied to this tool.

---

## 1. Threat model

**Assets:**
- the audit trail (`audit_logs`, `security_events`);
- the evidence (`evidence_chain`, `stage_evidence_links`);
- signed risk decisions (`risk_acceptances`);
- the secrets that guard them.

| ID | Adversary / failure | Today | After |
| --- | --- | --- | --- |
| T1 | **The app itself is compromised** (e.g. an injection bug) | It holds a superuser login, so it can rewrite or erase all evidence | The app login can only add and read evidence: **prevented** |
| T2 | **A leaked secrets file** (`.env` synced to OneDrive, plus its version history) | Superuser password inside, so full control | The file moves out of OneDrive and every value is rotated. A leaked app password could still **read all data** (including password hashes and audit content) and add records, but **not alter or erase evidence**. **Integrity protected; confidentiality only contained** *(corrected in the 2026-10-26 self-review: it first said "could only add records")* |
| T3 | **Someone with the owner or superuser password** | Silent edits possible (proven, §2 F1) | Edits become **detectable**: the hash chain breaks visibly |
| T4 | **Anyone with Docker or admin access to the host** | Full control (`docker exec psql` uses socket trust) | Unchanged by design: the host is the trust boundary. Edits are still **detectable** unless the whole chain is recomputed. Closing that needs an external anchor (§8, out of scope). |

## 2. Findings (all verified 2026-10-25)

| ID | Sev. | Finding | Evidence |
| --- | --- | --- | --- |
| F1 | **High** | The backend connects as `grc_admin`: **superuser** (also CREATEROLE, BYPASSRLS) and **owner** of every table. "Immutable" triggers stop the app's code, but this login can disable them. | On the test DB in a rolled-back transaction: a normal `UPDATE audit_logs` → "Audit record is immutable". The same login ran `ALTER TABLE … DISABLE TRIGGER` and then `UPDATE 1`. After rollback the trigger is confirmed enabled (`O`) and nothing changed. |
| F2 | **High** | **Schema setup fails open.** `init_db()` creates tables and triggers *at every app start*, using the app's own login, and its `except Exception` only logs. If trigger creation fails, the app runs with **no tamper protection**. | `core/database.py:105–220` |
| F3 | Medium | `security_events` (logins, failures, throttles, password changes) has **no** immutability trigger, so it can be edited or deleted. | `pg_trigger`: none on it. The code only INSERTs and SELECTs, so append-only breaks nothing. |
| F4 | Medium | There are **5** protected tables, not 3: `stage_evidence_links` has triggers too (missed in the first count), and `security_events` should. | `init_db` + `pg_trigger` |
| F5 | Medium | Live secrets are in the OneDrive-synced repo `.env`. Its 2026-10-25 01:26 version (new passwords) synced to the cloud. OneDrive also **re-created deleted files** here. | File attributes, timestamps; `Clarity_Cleanup_refactor.md` |
| F6 | Medium | Protection is **prevention only, no tamper evidence.** Anyone who gets past it (T3/T4) leaves no trace. | No hash or signature columns |
| F7 | Low | The backup container dumps as the superuser | `grc-db-backup` env |

## 3. Phase 0: failing tests first (RED today)

New file `backend/tests/test_db_posture.py`. Each test resolves **the role the backend is actually
configured with** (parsed from `docker exec <backend> printenv DATABASE_URL`, never assumed), then
acts as that role over the DB container's local socket. Writes happen only inside transactions that
are rolled back, and **only on the test stack** (refuses on `:8001`).

| Test | Asserts | Today |
| --- | --- | --- |
| `test_backend_role_is_not_superuser` | `rolsuper`, `rolcreaterole`, `rolcreatedb`, `rolbypassrls` are all false | 🔴 |
| `test_backend_role_owns_nothing` | owns no table, sequence or function in `public` | 🔴 |
| `test_backend_role_cannot_disable_triggers` | `ALTER TABLE <each of 5> DISABLE TRIGGER ALL` → "must be owner" | 🔴 |
| `test_backend_role_cannot_rewrite_evidence` | UPDATE / DELETE / TRUNCATE on each of the 5 → "permission denied" | 🔴 |
| `test_backend_role_can_append_and_read` | INSERT and SELECT on each of the 5 succeed (rolled back) | 🟢 (guards against over-restricting) |
| `test_all_protected_tables_have_enabled_triggers` | all 5 have enabled UPDATE/DELETE/TRUNCATE blockers | 🔴 (`security_events`) |
| `test_chain_verifies` | `fn_verify_chain(t)` reports intact for all 5 | 🔴 (doesn't exist) |
| `test_chain_detects_tamper` | as the **superuser**, rolled back: disable the trigger, edit one row, verify → reports the broken row | 🔴 |
| `test_chain_is_session_independent` | verify under two different session time zones → identical result, no false alarm | 🔴 |

Unit tests (no stack): `test_security_config.py` gains cases for the new startup guard (§5.4) and
for `_creds.py` refusing a secrets file under OneDrive (§4).

## 4. Phase 1: secrets out of OneDrive (F5)

- **New home:** `%USERPROFILE%\.secrets\grc-command-center.env`. The user-profile root isn't in
  OneDrive (it backs up Desktop and Documents only; checked in the registry). Restrict the ACL to
  the owner's account (`icacls /inheritance:r /grant:r <user>:F`).
- **Docker finds it automatically:** a persistent user environment variable
  `COMPOSE_ENV_FILES=%USERPROFILE%\.secrets\grc-command-center.env` (Compose v5.5.1 supports it;
  confirm with `docker compose config` at execution). If it's missing, compose already
  **refuses to start** (the `${VAR:?}` rules from 2026-10-25).
- **Tests and benchmark** (`backend/tests/_creds.py`): read `GRC_ENV_FILE`, else the first entry of
  `COMPOSE_ENV_FILES`. **Fail closed** if the resolved path is inside OneDrive. There's no fallback
  to the repo-root `.env`.
- **The old repo `.env`** is deleted, and **re-checked at the end of the session and again next
  session** (OneDrive restores).
- **Owner, outside the repo:** delete it from OneDrive's recycle bin *and* the file's version
  history (onedrive.com), and keep a copy of the new file's values in the password manager (now
  the backup).

## 5. Phase 2: least-privilege database roles (F1, F2, F7)

### 5.1 Roles

| Role | Login | Powers | Used by |
| --- | --- | --- | --- |
| `grc_admin` | yes | superuser (Postgres bootstrap) | **nothing running.** Break-glass only, via `docker exec`. Password rotated, kept in the password manager. |
| `grc_owner` | yes | owns every schema object; NOSUPERUSER | **only** the one-shot `db-migrate` service |
| `grc_app` | yes | NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS. Full read/write on ordinary tables. **SELECT + INSERT only** on the 5 protected tables. Sequence usage. EXECUTE on `fn_verify_chain`. | the backend (dev + test) |
| `grc_backup` | yes | member of `pg_read_all_data`, nothing else | `grc-db-backup` |

Role creation needs a superuser, so it's a one-time, idempotent `scripts/db_bootstrap_roles.py`. It
sends SQL over **stdin** via `docker exec` (passwords never appear in process arguments or output),
and is also mounted into `/docker-entrypoint-initdb.d/` so fresh volumes get the roles at first
boot. Ownership of all existing objects is transferred to `grc_owner`. `ALTER DEFAULT PRIVILEGES`
covers future tables.

### 5.2 Schema setup moves out of the app (fixes F2)

- New `backend/core/migrate.py`: runs `create_all`, the immutability triggers, the chain (Phase 3),
  the `stagestatus` enum value, and the grants, **as `grc_owner`**, then exits. Any error → exit
  code 1. **It no longer swallows failures.**
- `docker-compose-v2.yml` / `.test.yml` get a `db-migrate` service: same image,
  `command: python -m core.migrate`, `MIGRATE_DATABASE_URL` from the env file. The backend gets
  `depends_on: db-migrate: condition: service_completed_successfully`, so **the backend can't start
  on a failed migration**.
- The backend stops calling `init_db()`. Seeding (users, policies, TPRM stages) is ordinary
  reads and writes and stays in the backend.

### 5.3 Compose secrets (all required, `${VAR:?}`)

`GRC_ADMIN_PG_PASSWORD` (bootstrap), `GRC_OWNER_DB_PASSWORD`, `GRC_APP_DB_PASSWORD`,
`GRC_BACKUP_DB_PASSWORD`. The backend's `DATABASE_URL` uses **`grc_app`**. The **owner password
is never given to the backend container.**

### 5.4 Fail-closed startup guard

`core/security_config.py` gains `assert_db_posture()`, run in `lifespan()` before anything else
touches the DB. The backend **refuses to start** if its role:
- is superuser, CREATEROLE, CREATEDB or BYPASSRLS;
- owns any object in `public`;
- or if any of the 5 tables lacks an enabled UPDATE/DELETE/TRUNCATE blocker or the chain trigger.

The error names the failing check, never a value. This is what stops F1 or F2 from silently coming
back.

## 6. Phase 3: tamper-evident hash chain (F3, F4, F6)

On all **5** tables:
- **New columns:** `chain_seq bigint`, `prev_hash text`, `row_hash text` (nullable; pre-existing
  rows keep NULL).
- **`BEFORE INSERT` trigger `fn_chain_append()`:**
  - take a per-table transaction advisory lock, so concurrent inserts can't fork the chain;
  - `chain_seq = last + 1`;
  - `prev_hash` = the previous row's `row_hash`, or the table's **genesis seal** for the first
    chained row;
  - `row_hash = sha256(prev_hash ‖ canonical payload)`. Built-in `sha256()` (PG 16), no extension
    needed.
  - **Canonical payload, corrected in the 2026-10-26 self-review** (the first version said "the
    row as JSON", which has two defects):
    1. **Session-independent rendering.** Postgres prints `timestamp`/`timestamptz` in the
       *session's* `TimeZone`/`DateStyle`. A verifier in another time zone would compute different
       text and **raise a false tamper alarm**. Fix: both the append and verify functions declare
       `SET TimeZone = 'UTC'` and `SET DateStyle = 'ISO, YMD'`, and timestamps are hashed as
       explicit UTC ISO-8601 strings.
    2. **An explicit, versioned column list**, not the whole row. Hashing the whole row means any
       future `ADD COLUMN` changes the payload of *every old row* and breaks the chain. Each table's
       hashed columns are listed in `chain_genesis.columns` with a `chain_version`. A schema
       change that should be covered starts a new chain epoch (a new genesis row sealing the
       previous head), never a silent rehash.
  - **Unit test for this (§3):** verify the same rows under `SET TimeZone = 'America/New_York'`
    and `'Asia/Tokyo'` → identical hashes.
- **Genesis seal for the existing rows** (`audit_logs` 425, `evidence_chain` 155, `security_events`
  ~137, `risk_acceptances` 6, `stage_evidence_links` 2 on dev): `migrate.py` computes one SHA-256
  over all of them, in primary-key order, and records it in a new append-only table
  `chain_genesis(table_name, sealed_at, legacy_rows, seal_hash)`. Existing rows are never updated,
  so there's no trigger bypass during migration, yet they're now covered: any later edit changes
  the seal.
- **`fn_verify_chain(table) → (intact bool, first_bad_seq bigint, rows_checked bigint)`:**
  recomputes the seal and walks the chain.
- **It runs in three places:**
  - the tests (§3);
  - **`/readiness`**, a new `audit_chain` check (5/5 instead of 4/4; cheap at these sizes).
    `/readiness` is **unauthenticated**, so it returns only `intact`/`broken` per table, never
    sequence numbers, hashes or row details. Those come from the admin-only script;
  - `scripts/verify_audit_chain.py`, which also prints each table's **head hash**. Recording those
    heads somewhere the DB can't touch is what makes even T4 tampering detectable (§8).
- `security_events` also gets the UPDATE/DELETE/TRUNCATE blockers (F3).
- The superuser tamper tests in `smoke_test.py` / `test_tprm.py` stay as they are. They still
  prove the triggers block a direct edit.

## 7. Phase 4: rotate everything that touched OneDrive (once)

Generated with `secrets`, written straight into the new file, never printed:
- the 3 app account passwords (through `/auth/change-password`, which leaves an audit trail);
- `JWT_SECRET_KEY`;
- the `grc_admin` password;
- new `grc_owner`, `grc_app` and `grc_backup` passwords.

**Owner:** reissue the Groq API key in the Groq console and paste the new one into the new file.
The old key has been in OneDrive since August.

## 8. Verification (all must pass before the commit)

| Check | Expected |
| --- | --- |
| `test_db_posture.py` | all 🔴 → 🟢 |
| Backend booted with `DATABASE_URL` as `grc_admin` (throwaway container) | **refuses**: "database role is superuser" |
| `db-migrate` forced to fail (bad owner password, throwaway) | exits 1, and the backend never starts |
| `docker compose config` without `COMPOSE_ENV_FILES` | refuses (missing variables) |
| `_creds.py` pointed at a path under OneDrive | refuses |
| `/readiness` | 5/5, including `audit_chain` |
| `scripts/verify_audit_chain.py` | 5/5 intact; head hashes printed |
| **Backup restore drill:** latest backup (now made by `grc_backup`) restored into a throwaway Postgres, then verify | chain intact in the restored copy (proves backups work *and* carry the evidence) |
| Full `pytest` incl. `test_interview_sim.py` | all pass (Groq day) |
| `smoke_test.py` test + dev | 44/44 each (Groq day) |
| `test_pii` in dev | 21/21 |
| Repo `.env` | gone; still gone at the next session |

**Timing:** execution needs no Groq. The last three rows do, so either execute on a day with Groq
budget, or execute any time and run those rows (together with the still-pending checks from
2026-10-25) on the next Groq day.

## 9. Rollback

Roles and chain columns are **additive**: nothing is dropped. `git revert` plus a rebuild restores
the old code. But the old code's `init_db()` would then run as `grc_app` and fail, so a rollback
also points `DATABASE_URL` back at `grc_owner`. That's documented, not automated, on purpose:
a rollback should be a deliberate act.

## 10. Out of scope, named on purpose

- **External anchoring of chain heads** (WORM storage, or a signed commit to a *private* repo), so
  that even a host admin who recomputes the whole chain is caught. This is the T4 answer; next step
  after this one.
- Row-level security, TLS on the internal DB network (the DB isn't published to the host).
- The **DevSecOps pipeline**: next draft. It runs §3's tests, the unit tests, secret scanning,
  Trivy and the SBOM on every push.
- Mufasa and other projects' `.env` files under OneDrive: same issue, not this repo, owner's call.

## 11. Execution record (2026-10-31)

**Order:** branch → failing tests (red) → code → test stack → dev stack → rotation → negative
checks → fresh-volume drill → backup restore drill → the Groq checks → docs.

**Red first (before any fix):** `test_db_posture.py` 30 failed / 9 passed (the 9 were the
"can still append and read" guards and the four tables that already had blockers);
`test_repo_policy.py` 7 new rules failed; `test_creds_resolution.py` 3 of 4 failed;
the startup-guard unit tests failed at import (the guard didn't exist).

**Verification (§8), all on 2026-10-31:**

| Check | Result |
| --- | --- |
| `test_db_posture.py`, test stack | **39/39** (was 30 red) |
| `test_db_posture.py`, dev (read-only subset) | 12 passed, 27 write checks skipped by design |
| Backend started as `grc_admin` (throwaway `compose run`) | refused, exit 3: "database role has rolsuper; … rolcreaterole; … rolcreatedb; … rolbypassrls" |
| Backend started as `grc_owner` | refused, exit 3: "database role owns objects in schema public" |
| `db-migrate` with a wrong owner password | exit 1, "nothing applied" |
| `db-migrate` as `grc_app` | exit 1 ("must be owner of type stagestatus") |
| **Fresh-volume drill** (throwaway `grc-drill` project, own volumes) | first boot ran `10-roles.sh` from `docker-entrypoint-initdb.d`; with a failing migration `up` exited 1 and the backend stayed **Created, never started**; with the migration fixed, the backend came up healthy and the posture checks passed. Drill containers, volumes and images removed; `grc-faiss` untouched |
| `docker compose config` without `COMPOSE_ENV_FILES` | exit 1, names every missing variable |
| `_creds.py` given a path under OneDrive | refuses (unit test, both `GRC_ENV_FILE` and `COMPOSE_ENV_FILES`) |
| `/readiness` (dev) | `ready`, 6/6 checks including `audit_chain` ("5/5 tables intact") |
| `scripts/verify_audit_chain.py`, dev and test | ALL INTACT; chains growing in real use (dev after the smoke run: audit_logs 14 chained rows, security_events 22, risk_acceptances 1) |
| **Backup restore drill**: backup taken by `grc_backup`, restored into a throwaway Postgres (no network) | restored cleanly; `fn_verify_chain` intact on all 5 tables in the copy |
| Full `pytest` on the test stack, nothing deselected | **186 passed, 6 skipped** (was 107 + 6 with the Groq test deselected) |
| `smoke_test.py` test / dev | **44/44** / **44/44** |
| `test_pii` in the dev container | **23/23** (the "21/21" in §8 above was stale) |
| Unit suite (`-m "not integration"`) | 97 passed, 6 skipped |
| Repo `.env` | deleted; re-check next session (OneDrive restores deletions) |

**Rotated:** the three app account passwords (through `/auth/change-password` on both stacks,
so each change is in `security_events`, now chained), `JWT_SECRET_KEY`, the `grc_admin` password,
and new `grc_owner` / `grc_app` / `grc_backup` passwords. All generated with `secrets` and written
straight into the new file; none printed. **Not rotated here (owner):** the Groq API key (§7).

**Where execution differs from the draft, and why:**
- **Role bootstrap is a shell script, `docker/db-init/10-roles.sh`, not `scripts/db_bootstrap_roles.py`.**
  The Postgres image has no Python, so a Python script couldn't run from
  `docker-entrypoint-initdb.d`; one shell script now serves both a fresh volume and (run once by
  hand) an existing one. Passwords reach `psql` through `\getenv`, never in arguments.
- **Ownership transfer** uses `ALTER DATABASE … OWNER TO grc_owner` (so it owns schema `public`)
  plus per-object `ALTER … OWNER`, because `REASSIGN OWNED` isn't allowed for the bootstrap
  superuser.
- **No `ALTER DEFAULT PRIVILEGES`:** `core/migrate.py` re-applies the grants on every run instead,
  so a new protected table never inherits UPDATE/DELETE by default.
- **The genesis seal also binds the table name**, and `chain_genesis` itself is append-only (same
  three blockers).
- **`/readiness` has 6 checks, not 5:** PII redaction was added after this draft.
- **Two images:** `db-migrate` and the backend build from the same Dockerfile under separate tags
  (the layers are shared; the second build is instant).

**Found during execution:**
- **The old repo `.env` held a stray line with an unrelated credential** (not used by the stack).
  It was not carried into the new file; the owner revokes it. That line also had **no `=`**, so
  since 2026-10-28 every `docker compose` command would have failed to parse the file; the
  running stacks had been started before then.
- `tests/conftest.py`, `smoke_test.py` and `test_tprm.py` keep using `docker exec … psql -U grc_admin`
  over the socket: that's the host trust boundary (T4), by design.

**Rollback** (§9) is unchanged. A pre-change backup (taken as the superuser, before any change) is
in the `grc-db-backups` volume: `grc_audit-20261031-200422.sql.gz`.
