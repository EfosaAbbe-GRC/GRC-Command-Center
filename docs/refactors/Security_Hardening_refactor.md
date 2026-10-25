# Security hardening: network exposure, credentials, secrets in images, login throttling

**Status:** **EXECUTED 2026-10-25** (EXECUTE from Efosa). Kept out of the repo while it was a
draft, since it described live weaknesses, and published together with the fix. Found during a
security sweep that began with removing a tracked SQLite file (`fa6ee8d`).

**Verified at execution** (dev = `:8001`, test = `:8002`):

| Check | Result |
| --- | --- |
| Port bindings | `127.0.0.1:8001`, `127.0.0.1:3006`, `127.0.0.1:8002`. The host's own LAN address refuses all three. |
| `/app/.env` in images | absent in both new images. A stale 2-month-old test image that still had it was removed. Every remaining GRC image is clean. |
| Accounts rotated | 6/6 via `/auth/change-password` (3 roles × 2 stacks), each leaving a `PASSWORD_CHANGE` trail. JWT secret and Postgres role password rotated on both DBs. Backup container connects with the new one. |
| Old public password | `401` |
| 5 wrong logins (probe username) | 5× `401`, then `429`, `Retry-After: 888`. Another user is unaffected (`200`). |
| Change password: short / same / public | `422` (schema) / `400` / `400` |
| Boot with `ADMIN_PASSWORD=grc-admin-2026` | refused: "ADMIN_PASSWORD is a publicly known value", value not printed, exit 3 |
| `docker compose config` with `ADMIN_PASSWORD` empty | refused: "set ADMIN_PASSWORD in .env" |
| `pytest` (all but `test_interview_sim.py`) | **76 passed, 1 skipped** = old 60 + 17 new. Reconciled against the 72-test baseline. |
| Not yet run (Groq budget spent by the same day's v11) | `test_interview_sim.py` (12), smoke on test and dev (44/44 each), `test_pii` (21/21). **Run on the next fresh Groq day.** |

Two corrections made at execution: F3 below (the baked file's Google key line was empty), and the
README, which said to create `backend/.env` (the very file that got baked in) and that placeholder
passwords "won't log in" (an account seeded with one would). `GOOGLE_API_KEY` is no longer passed
into the containers, since no live code path reads it.

**Timing:** execute **after** the v11 benchmark finishes. S1/S2 restart containers and S9 rotates
the passwords the benchmark logs in with. Smoke verification costs ~9k Groq tokens per run, so on a
benchmark day run at most one; the rest can wait for the next day.

---

## Findings (all verified 2026-10-25, not inferred)

| ID | Severity | Finding | Evidence |
| --- | --- | --- | --- |
| F1 | **High** | Backend `:8001`, test backend `:8002` and frontend `:3006` are published on `0.0.0.0`: reachable from every device on the host's network, not just the host. | `docker ps` shows `0.0.0.0:8001->8001`. The host's Wi-Fi uses the Windows *Public* firewall profile, and Docker Desktop has an inbound **Allow** rule on that profile. |
| F2 | **High** | All three live accounts (dev **and** test) use the passwords hard-coded in the public repo's tests. | Effective settings inside `grc-backend` compare equal to the public strings. An admin login with them succeeded at 00:04. 33 lines across 11 test/benchmark files, plus the legacy compose file. |
| F3 | **Medium** | `backend/.env` is **baked into the backend images** at `/app/.env`: the (public) passwords and an **old, unused** JWT secret (43 chars; the live one comes from compose, 64 chars). Its `GOOGLE_API_KEY` line is empty. *Corrected at execution: the draft first said it held the Google key.* | `.dockerignore`'s `.env` / `*.env` match the build-context root only, so `COPY backend/ .` carries `backend/.env` in. It's the same anchoring mistake as the `.gitignore` fixed in `fa6ee8d`. The images are local only (never pushed). |
| F4 | **Medium** | Fresh-install fail-open: `docker-compose-v2.yml` never passes `*_PASSWORD`, so a clone seeds accounts with the placeholder `CHANGE-ME-SET-IN-ENV`, which is published in `config.py`. Its comment says a missing `.env` "fails loudly"; it doesn't. The same pattern applies to `POSTGRES_PASSWORD:-grc_password_2026`. | `main.py:67–75` seeds whatever `settings` holds, with no check. |
| F5 | **Medium** | No throttling on `/auth/login`. Failures are logged and nothing else happens. | No `@limiter.limit` on the route, and no failure counter. |
| F6 | **Medium** | **IP-keyed rate limiting is ineffective here.** Docker Desktop NATs every inbound connection to the bridge gateway, so all clients share one address. That makes the existing `5/minute` (ingest) and `10/minute` limits global, and a per-IP login limit would be useless or self-DoS. | `security_events`: every login since 2026-08-14 shows `172.22.0.1` (or `127.0.0.1`). |
| F7 | Low | No password policy on change: empty, short, identical-to-old or a known-public password are all accepted. | `ChangePasswordRequest` is two bare `str` fields. |
| F8 | Low | Username-enumeration timing: an unknown user returns before any bcrypt work, so it answers measurably faster than a known user. | `auth.py:authenticate_user` returns `None` before `verify_password`. |
| F9 | Low | `backend/pytest_output.txt` (stale, contains the public passwords) and the undocumented legacy `docker-compose.yml` (public password defaults) are tracked. | `git ls-files`. README documents only `docker-compose-v2.yml`. |

**Checked and fine:** no API key, private key or `.env` in any tracked file **or anywhere in git
history**. The live JWT secret is custom and 64 chars. Postgres is not published to the host.
CORS allows localhost origins only. Passwords are bcrypt-hashed. The access-token lifetime is 15
min. The backend runs as non-root `grcuser`.

**Has anyone else tried?** No evidence of it: every `LOGIN_FAIL` is the test suite's own negative
check (`hacker` ×3, `admin` ×1). **Limit:** because of F6, the log can't distinguish the host from
another device on the network, so this is an absence of evidence, not proof.

## Principles applied

1. **Least exposure:** listen only where a user actually is (loopback).
2. **Fail closed:** refuse to start insecurely rather than run with a known secret (the same posture
   as PII redaction's 503).
3. **Secrets never in code, images or git:** injected at runtime from one gitignored file.
4. **Defense in depth:** exposure, credentials, throttling and policy are each fixed independently,
   so one regression doesn't reopen the hole.
5. **Rotate anything that was exposed,** don't just hide it.

---

## Changes

### S1. Bind published ports to loopback (F1)

`docker-compose-v2.yml`:

```yaml
-      - "8001:8001"
+      - "127.0.0.1:8001:8001"
...
-      - "3006:3006"
+      - "127.0.0.1:3006:3006"
```

`docker-compose.test.yml`: `"8002:8001"` → `"127.0.0.1:8002:8001"`.

No functional impact on the host. The browser calls `http://localhost:8001` (`src/lib/api.js`),
nginx proxies `/api/` to `backend:8001` over the internal Docker network, and every test or script
targets `localhost`. Uvicorn keeps `--host 0.0.0.0` *inside* the container, which it needs so
Docker can forward to it. The exposure was the host-side publish, and that's what changes.

### S2. Keep secrets out of images (F3)

`.dockerignore`:

```gitignore
 # Secrets — never in image
-.env
-*.env
+# Unanchored: `.env` alone matched the context root only, so backend/.env was baked in.
+**/.env
+**/*.env
 secrets/
...
 # Runtime data — mounted as volumes, not baked into image
-backend/data/grc_audit.db
+**/*.db
+**/*.db-*
```

Rebuild both backend images. **Verify:** `docker exec grc-backend test -e /app/.env` exits non-zero.
Then run `docker image prune` so the old layers that still hold the file are gone. Only *dangling*
images are removed; nothing that is tagged or running.

### S3. Inject secrets explicitly, required, no public fallbacks (F2, F4)

`docker-compose-v2.yml` and `docker-compose.test.yml`, backend `environment:`. `${VAR:?msg}` makes
`docker compose` itself refuse to start when the value is missing:

```yaml
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:?set JWT_SECRET_KEY in .env}
+     - ADMIN_PASSWORD=${ADMIN_PASSWORD:?set ADMIN_PASSWORD in .env}
+     - ANALYST_PASSWORD=${ANALYST_PASSWORD:?set ANALYST_PASSWORD in .env}
+     - VIEWER_PASSWORD=${VIEWER_PASSWORD:?set VIEWER_PASSWORD in .env}
```

All `POSTGRES_PASSWORD:-grc_password_2026` (db, backup, `DATABASE_URL`) →
`POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env`.

One source of truth: the repo-root `.env` (gitignored, read by compose). `backend/.env` is
retired (see S9 step 6).

### S4. Fail closed at startup on insecure configuration (F4)

New `backend/core/security_config.py`, called first thing in `lifespan()`. It runs at app startup,
**not** at import, so host-side pytest that imports `core.*` is unaffected:

```python
"""Refuse to start with a configuration that is known to be insecure.

Runs at app startup (lifespan), not at import, so tooling that imports core.*
without a full environment keeps working.
"""
from core.config import settings

# Every password value that has ever been public: placeholders in config.py and
# the defaults hard-coded in this repo's tests and legacy compose file before
# 2026-10-25. Rejecting them is what makes the rotation stick.
KNOWN_PUBLIC_PASSWORDS = frozenset({
    "CHANGE-ME-SET-IN-ENV",
    "grc-admin-2026", "grc-admin-new-2026", "grc-analyst-2026", "grc-viewer-2026",
})
JWT_PLACEHOLDER = "CHANGE-ME-IN-PRODUCTION-USE-A-REAL-SECRET"
MIN_PASSWORD_LEN = 12
MIN_JWT_SECRET_LEN = 32


def password_problem(pw: str) -> str | None:
    if pw in KNOWN_PUBLIC_PASSWORDS:
        return "is a publicly known value"
    if len(pw) < MIN_PASSWORD_LEN:
        return f"is shorter than {MIN_PASSWORD_LEN} characters"
    if len(pw.encode("utf-8")) > 72:
        return "is longer than bcrypt's 72-byte limit"
    return None


def assert_secure_config() -> None:
    problems = []
    if settings.AUTH_ENABLED is not True:
        problems.append("AUTH_ENABLED is off")
    jwt = settings.JWT_SECRET_KEY
    if jwt == JWT_PLACEHOLDER or len(jwt) < MIN_JWT_SECRET_LEN:
        problems.append(f"JWT_SECRET_KEY is the placeholder or under {MIN_JWT_SECRET_LEN} chars")
    for name in ("ADMIN_PASSWORD", "ANALYST_PASSWORD", "VIEWER_PASSWORD"):
        why = password_problem(getattr(settings, name))
        if why:
            problems.append(f"{name} {why}")
    if problems:
        # Names only, never values.
        raise RuntimeError("Insecure configuration, refusing to start: " + "; ".join(problems))
```

`main.py` `lifespan()`:

```python
 async def lifespan(app):
     logger.info("System startup", version=settings.VERSION, mode="POSTGRES_V2")
+    assert_secure_config()
```

### S5. Detect accounts still on a public password (F2, defense in depth)

S4 checks the *configured* values, but an existing account keeps whatever hash it already has (the
seeding only creates missing accounts). So also in `lifespan()`, after seeding: for each seeded
username, if its stored hash verifies against any `KNOWN_PUBLIC_PASSWORDS` entry, set
`must_change_password=True` and log a `CRITICAL` `PUBLIC_PASSWORD_DETECTED` security event. It
reuses the existing forced-reset flow (`set_must_change_password`, which `update_password` clears).
Cost: about five bcrypt checks per account at boot (~0.3 s each).

### S6. Login throttling keyed on username (F5, F6, F8)

New `backend/core/login_throttle.py`. It's in-memory, which is correct because the backend runs
`--workers 1`. A multi-worker deployment would need a shared store (note this in a comment):

- **5 failures in 15 min** for a username → `429` with `Retry-After`, a `LOGIN_THROTTLED` security
  event, and **no** password check while throttled.
- It's a **throttle, not a permanent lockout** (OWASP Authentication Cheat Sheet), so nobody can
  lock the admin out indefinitely by guessing wrong on purpose. The window expires on its own.
- A **success clears** the counter. Only failures count, so the many successful logins in
  smoke/pytest are unaffected.
- It's keyed on the username, lowercased, because of F6 (every client shares one IP here). A
  global backstop of **50 failures/15 min across all usernames** catches spraying many usernames.

Plus F8: `authenticate_user` runs `verify_password` against a fixed dummy bcrypt hash when the user
doesn't exist, so unknown and known usernames take the same time. The response stays the same
generic `401 Invalid credentials`.

### S7. Password policy on change (F7)

`schemas.py`:

```python
 class ChangePasswordRequest(BaseModel):
     old_password: str
-    new_password: str
+    new_password: str = Field(min_length=12, max_length=64)
```

`change_password()` additionally rejects `new == old` and anything `password_problem()` flags
(`400`, with a reason that never echoes the password).

### S8. No credentials in tests or tools (F2)

New `backend/tests/_creds.py`. It reads `GRC_ADMIN_PASSWORD` / `GRC_ANALYST_PASSWORD` /
`GRC_VIEWER_PASSWORD` from the environment, falling back to `ADMIN_PASSWORD` etc. parsed from the
repo-root `.env`. **There is no hard-coded fallback:** if neither is present it fails with a clear
message instead of trying a public default. Replace every literal in:

`smoke_test.py` (8), `test_iam_05.py` (6), `test_auth.py`, `test_tprm.py`, `test_interview_sim.py`
(3 each), `test_iam_07/08/09/10.py` (2 each), `test_executive.py`, `rag_benchmark.py` (1 each).

`test_iam_05.py`'s rotate-and-restore uses `ADMIN + "-rotated-x"` instead of a second literal.
`smoke_test.py`'s deliberate wrong login (`hacker` / `wrong`) stays as it is; it isn't a credential.

New tests: `test_security_config.py` (placeholder, public, short and over-72-byte values are each
rejected; good values pass) and throttle tests (5 fails → 429; success resets; a different
username is unaffected; the window expires). These are pure unit tests with no stack or Groq.

### S9. Rotate everything that was exposed (execution runbook, not code)

In order. Generate secrets locally with Python's `secrets` module, write them straight into `.env`,
and never print them to a terminal or a log:

1. New admin, analyst and viewer passwords (`secrets.token_urlsafe(18)`, 24 chars) go into the
   root `.env`. **Efosa stores them in a password manager.**
2. Change each account on **dev and test** through `/api/v1/auth/change-password` (old public →
   new), which leaves a `PASSWORD_CHANGE` audit trail.
3. New `JWT_SECRET_KEY` (`secrets.token_hex(32)`). The old one sat in an image layer. Rotating it
   only ends current sessions.
4. New `POSTGRES_PASSWORD`, applied with `ALTER ROLE grc_admin PASSWORD …` inside `grc-db-pg` and
   `grc-db-pg-test` before restarting, so the backend and the backup container reconnect with it.
   (The DB was never published, but the old value is public.)
5. Rebuild and restart: `docker compose -f docker-compose-v2.yml up -d --build`, then the same for
   the test stack.
6. **Retire `backend/.env`.** Anything in it still needed moves to the root `.env`, then the file is
   **destroyed, not archived**. This is the one deliberate exception to archive-don't-delete: an
   archived secrets file is still a live secrets file. *Efosa's decision.*
7. **Efosa, outside the repo:** revoke the old `GOOGLE_API_KEY` in Google Cloud Console → APIs &
   Services → Credentials. The project is believed shut off, but revoking costs nothing and closes
   it for certain.

### S10. Untrack stale credential-bearing files (F9)

`git rm --cached backend/pytest_output.txt` (stale output that holds the old passwords) and
`git rm docker-compose.yml` (undocumented legacy, superseded by `docker-compose-v2.yml`, has public
password defaults). Git history keeps both for reference.

---

## Verification (all must pass before the commit)

| Check | Expected |
| --- | --- |
| From another device on the same network: `http://<host LAN IP>:8001/api/v1/health` | **Fails to connect** (before: JSON) |
| `docker exec grc-backend test -e /app/.env` | non-zero (the file is absent) |
| Boot the test stack with `ADMIN_PASSWORD=grc-admin-2026` | Backend **refuses to start**, naming `ADMIN_PASSWORD`, without printing its value |
| `docker compose config` with `ADMIN_PASSWORD` unset | compose errors `set ADMIN_PASSWORD in .env` |
| Login with an old public password | `401` |
| 6 wrong logins for one user | 6th → `429` + `Retry-After`; `LOGIN_THROTTLED` logged |
| Change password to `short` / the same / a public value | `400` / `400` / `400` |
| `git grep -nE "grc-(admin\|analyst\|viewer)-2026"` | only history docs (refactor drafts and this file), no code or tests |
| `pytest` from `backend/` | **71 + new tests pass**, 1 skipped |
| `smoke_test.py` on test stack, then dev | **44/44** each (~9k Groq tokens each, so next day if a benchmark ran) |
| `test_pii` in the dev container | **21/21** |

## Rollback

Every change is a file edit plus a rebuild. `git revert` the commit and rebuild. Credential
rotation isn't rolled back (the old values are public). If the new passwords are lost, use
`force_reset_util.py` inside the container, then update the password directly with a fresh bcrypt
hash.

## Deliberately out of scope (candidates for later)

- **Rewriting git history:** decided against 2026-09-29. Everything removed here stays in old
  commits, so rotation (S9), not removal, is what neutralizes the exposed values.
- Dependency lock file and image digest pinning (already an open hardening item).
- nginx security headers (CSP, `X-Frame-Options`), HTTPS/TLS. Loopback-only makes these
  lower-value for a local dev stack.
- MFA and per-user accounts beyond the three seeded roles.
- Fixing the IP-keyed limits on `/ingest` (F6 makes them global). Harmless today; revisit if the
  stack is ever multi-user.
