"""Database privilege posture and the tamper-evident audit chain (Secrets_DB_Privilege_refactor.md §3).

Each test resolves the role the backend is ACTUALLY configured with (parsed from the backend
container's DATABASE_URL, never assumed), then acts as that role over the DB container's local
socket. The password in that URL is never printed or stored.

Read-only checks run against whichever stack GRC_TEST_BASE names. Anything that writes runs only
on the isolated test stack (:8002), only inside a transaction that is rolled back.
"""
import os
import subprocess
from urllib.parse import urlparse

import pytest

# Needs the live stack -- CI's unit job deselects it (see pyproject.toml).
pytestmark = pytest.mark.integration

BASE = os.environ.get("GRC_TEST_BASE", "http://localhost:8002")
IS_TEST_STACK = ":8002" in BASE
DB_CONTAINER = os.environ.get(
    "GRC_TEST_DB_CONTAINER", "grc-db-pg-test" if IS_TEST_STACK else "grc-db-pg")
DB_NAME = os.environ.get(
    "GRC_TEST_DB_NAME", "grc_audit_test" if IS_TEST_STACK else "grc_audit")
BACKEND_CONTAINER = os.environ.get(
    "GRC_TEST_BACKEND_CONTAINER", "grc-backend-test" if IS_TEST_STACK else "grc-backend")
SUPERUSER = "grc_admin"

PROTECTED = ["audit_logs", "evidence_chain", "security_events", "risk_acceptances",
             "stage_evidence_links", "risk_events"]
# Editable registers whose history lives elsewhere: the app may change rows, never remove them.
NO_DELETE = ["risks", "entities"]
CHAIN_COLUMNS = ("chain_seq", "prev_hash", "row_hash")

writes_only_on_test_stack = pytest.mark.skipif(
    not IS_TEST_STACK, reason="writes (even rolled back) run only on the test stack, never dev")


@pytest.fixture(scope="module", autouse=True)
def _one_risk_event_on_test_stack():
    """The append check copies an existing row; a fresh test DB has no risk_events yet
    (Risk_Register_refactor.md R7). Create one risk through the API, test stack only."""
    if not IS_TEST_STACK:
        return
    import uuid
    import requests
    from tests._creds import ANALYST_PASS
    v1 = f"{BASE}/api/v1"
    try:
        tok = requests.post(f"{v1}/auth/login", json={"username": "analyst", "password": ANALYST_PASS},
                            timeout=30).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        ent = requests.post(f"{v1}/entities", headers=h, timeout=30, json={
            "name": f"posture-seed-{uuid.uuid4().hex[:8]}", "entity_type": "process"}).json()
        requests.post(f"{v1}/risks", headers=h, timeout=30, json={
            "title": "posture seed", "statement": "Seed row for the append check.",
            "category": "operational", "entity_id": ent["id"], "owner": "pytest",
            "inherent_likelihood": 1, "inherent_impact": 1})
    except Exception:
        pass  # the append check below then fails loudly with "no row to copy"


def _psql(role, sql):
    """Run `sql` as `role` over the container's local socket. Returns (ok, output)."""
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", DB_CONTAINER, "psql", "-U", role, "-d", DB_NAME,
             "-v", "ON_ERROR_STOP=1", "-At", "-q"],
            input=sql, capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        pytest.skip(f"docker/psql unavailable: {e}")
    return r.returncode == 0, (r.stdout + r.stderr).strip()


@pytest.fixture(scope="module")
def app_role():
    try:
        r = subprocess.run(["docker", "exec", BACKEND_CONTAINER, "printenv", "DATABASE_URL"],
                           capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        pytest.skip(f"docker unavailable: {e}")
    if r.returncode != 0:
        pytest.skip(f"{BACKEND_CONTAINER} not running")
    role = urlparse(r.stdout.strip()).username
    assert role, "could not parse a role from the backend's DATABASE_URL"
    return role


def _insert_copy_sql(table):
    """INSERT one copy of an existing row (new primary key). Chain columns are left to the trigger."""
    ok, out = _psql(SUPERUSER, f"""
        SELECT string_agg(quote_ident(column_name), ',' ORDER BY ordinal_position)
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = '{table}'
          AND column_name NOT IN ('id', {", ".join(f"'{c}'" for c in CHAIN_COLUMNS)});
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = '{table}' AND column_name = 'id';
    """)
    assert ok, out
    cols, id_type = out.splitlines()
    if id_type == "uuid":
        return (f"INSERT INTO {table} (id, {cols}) "
                f"SELECT gen_random_uuid(), {cols} FROM {table} ORDER BY id LIMIT 1 RETURNING 'appended';")
    return f"INSERT INTO {table} ({cols}) SELECT {cols} FROM {table} ORDER BY id LIMIT 1 RETURNING 'appended';"


# ── F1: the backend's role must not be able to rewrite its own evidence ─────────────────
def test_backend_role_is_not_superuser(app_role):
    ok, out = _psql(app_role, "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls "
                              "FROM pg_roles WHERE rolname = current_user;")
    assert ok, out
    assert out == "f|f|f|f", f"{app_role} has super/createrole/createdb/bypassrls flags: {out}"


def test_backend_role_owns_nothing(app_role):
    ok, out = _psql(app_role, """
        SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relowner = r.oid)
             + (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proowner = r.oid)
             + (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = 'public' AND t.typowner = r.oid)
        FROM pg_roles r WHERE r.rolname = current_user;""")
    assert ok, out
    assert out == "0", f"{app_role} owns {out} objects in public (an owner can disable triggers)"


@writes_only_on_test_stack
@pytest.mark.parametrize("table", PROTECTED)
def test_backend_role_cannot_disable_triggers(app_role, table):
    ok, out = _psql(app_role, f"BEGIN; ALTER TABLE {table} DISABLE TRIGGER ALL; ROLLBACK;")
    assert not ok and "must be owner" in out, f"{app_role} could disable triggers on {table}: {out}"


@writes_only_on_test_stack
@pytest.mark.parametrize("table", PROTECTED)
@pytest.mark.parametrize("statement", ["UPDATE {t} SET id = id WHERE false",
                                       "DELETE FROM {t} WHERE false",
                                       "TRUNCATE {t}"])
def test_backend_role_cannot_rewrite_evidence(app_role, table, statement):
    # A privilege error, not the trigger: the role must not hold the right at all.
    ok, out = _psql(app_role, f"BEGIN; {statement.format(t=table)}; ROLLBACK;")
    assert not ok and "permission denied" in out, \
        f"{app_role}: `{statement.format(t=table)}` was not refused by privilege: {out}"


@writes_only_on_test_stack
@pytest.mark.parametrize("table", NO_DELETE)
def test_backend_role_cannot_delete_register_rows(app_role, table):
    # Risk_Register_refactor.md T2: a risk is closed with a reason, never removed.
    ok, out = _psql(app_role, f"BEGIN; DELETE FROM {table} WHERE false; ROLLBACK;")
    assert not ok and "permission denied" in out, f"{app_role} may DELETE from {table}: {out}"


@writes_only_on_test_stack
@pytest.mark.parametrize("table", NO_DELETE)
def test_backend_role_can_still_edit_register_rows(app_role, table):
    ok, out = _psql(app_role, f"BEGIN; UPDATE {table} SET id = id WHERE false; ROLLBACK;")
    assert ok, f"{app_role} lost UPDATE on {table}: {out}"


@writes_only_on_test_stack
@pytest.mark.parametrize("table", PROTECTED)
def test_backend_role_can_append_and_read(app_role, table):
    # Guards against over-restricting: the app must still add and read evidence.
    ok, out = _psql(app_role, f"BEGIN; SELECT count(*) >= 0 FROM {table}; "
                              f"{_insert_copy_sql(table)} ROLLBACK;")
    assert ok, f"{app_role} could not append to / read {table}: {out}"
    assert "appended" in out.splitlines(), f"{table} has no row to copy; the check proved nothing"


# ── F2/F3/F4: every protected table has its blockers, enabled ───────────────────────────
@pytest.mark.parametrize("table", PROTECTED)
def test_all_protected_tables_have_enabled_triggers(table):
    # tgtype bits: 8 DELETE, 16 UPDATE, 32 TRUNCATE. tgenabled 'D' = disabled.
    ok, out = _psql(SUPERUSER, f"""
        SELECT bool_or(tgtype & 16 > 0), bool_or(tgtype & 8 > 0), bool_or(tgtype & 32 > 0)
        FROM pg_trigger
        WHERE tgrelid = '{table}'::regclass AND tgenabled <> 'D'
          AND tgfoid = 'fn_prevent_immutability_violation'::regproc;""")
    assert ok, out
    assert out == "t|t|t", f"{table}: UPDATE|DELETE|TRUNCATE blockers enabled = {out or 'none'}"


# ── F6: tamper evidence ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("table", PROTECTED)
def test_chain_verifies(app_role, table):
    ok, out = _psql(app_role, f"SELECT intact FROM fn_verify_chain('{table}');")
    assert ok and out == "t", f"{table}: chain not intact or verifier missing: {out}"
    ok, out = _psql(SUPERUSER, f"""
        SELECT count(*) FROM pg_trigger
        WHERE tgrelid = '{table}'::regclass AND tgenabled <> 'D' AND tgtype & 4 > 0
          AND tgfoid = 'fn_chain_append'::regproc;""")
    assert ok and out == "1", f"{table}: enabled chain-append INSERT trigger count = {out}"


@writes_only_on_test_stack
def test_chain_detects_tamper():
    """As the superuser, in a rolled-back transaction: bypass the trigger, edit, verify."""
    # 1. A legacy row (sealed in chain_genesis) edited -> the seal breaks, reported as seq 0.
    ok, out = _psql(SUPERUSER, """
        BEGIN;
        ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_no_update;
        UPDATE audit_logs SET response = response || ' (edited)'
          WHERE id = (SELECT min(id) FROM audit_logs WHERE chain_seq IS NULL);
        SELECT intact, first_bad_seq FROM fn_verify_chain('audit_logs');
        ROLLBACK;""")
    assert ok, out
    assert out.splitlines()[-1] == "f|0", f"legacy-row edit not detected: {out}"

    # 2. A chained row edited -> verification names that row's sequence number.
    ok, out = _psql(SUPERUSER, """
        BEGIN;
        INSERT INTO audit_logs (request_id, query, response) VALUES ('tamper-probe', 'q', 'r');
        ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_no_update;
        UPDATE audit_logs SET response = 'rewritten' WHERE request_id = 'tamper-probe';
        SELECT (SELECT chain_seq FROM audit_logs WHERE request_id = 'tamper-probe')
               = first_bad_seq, intact FROM fn_verify_chain('audit_logs');
        ROLLBACK;""")
    assert ok, out
    assert out.splitlines()[-1] == "t|f", f"chained-row edit not detected at its sequence: {out}"


@writes_only_on_test_stack
def test_chain_is_session_independent(app_role):
    """A row written in one session time zone verifies in another: no false tamper alarm.
    risk_acceptances has timestamptz columns, whose text form follows the session TimeZone."""
    ok, out = _psql(app_role, f"""
        BEGIN;
        SET LOCAL TimeZone = 'Asia/Tokyo';
        {_insert_copy_sql('risk_acceptances')}
        SET LOCAL TimeZone = 'America/New_York';
        SELECT intact FROM fn_verify_chain('risk_acceptances');
        ROLLBACK;""")
    assert ok, out
    assert out.splitlines()[-1] == "t", f"verification depends on the session time zone: {out}"
