"""One-shot schema migration: run as grc_owner by the db-migrate service, then exit.

Until 2026-10-31 the backend set up the schema itself, at every start, as a superuser that owned
every table, and only logged a failure (Secrets_DB_Privilege_refactor.md F1, F2). Now:

- this module is the only code that changes the schema. It runs as `grc_owner`, which owns the
  tables but is not a superuser;
- the backend connects as `grc_app`, which can add and read evidence but not alter, delete,
  truncate or un-protect it, and refuses to start if that ever stops being true
  (core.security_config.assert_db_posture);
- everything below runs in ONE transaction: either all of it applies or none of it does, and any
  error exits 1, so compose never starts the backend on a half-migrated database.

Usage (inside the image): python -m core.migrate     (needs MIGRATE_DATABASE_URL)
"""
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from core.models import Base
import core.tprm            # noqa: F401  registers the TPRM models on Base.metadata
import core.interview_sim   # noqa: F401  registers the Interview Simulator models
from core.security_config import PROTECTED_TABLES

APP_ROLE = "grc_app"
CHAIN_VERSION = 1
CHAIN_COLUMNS = ("chain_seq", "prev_hash", "row_hash")

# Trigger-name prefixes. The first four are the names already installed since April/August.
BLOCKER_PREFIX = {
    "audit_logs": "trg_audit",
    "evidence_chain": "trg_evidence",
    "risk_acceptances": "trg_risk_acc",
    "stage_evidence_links": "trg_stage_evidence",
    "security_events": "trg_security_events",    # new: F3, it had no protection at all
    "chain_genesis": "trg_chain_genesis",        # new: the seals are evidence too
}

# Hashing must not depend on the session that happens to run it: timestamptz renders in the
# session's TimeZone, so a verifier in another zone would raise a false tamper alarm.
DETERMINISTIC = """
    SET TimeZone = 'UTC' SET DateStyle = 'ISO, YMD' SET IntervalStyle = 'postgres'
    SET extra_float_digits = 1"""

FUNCTIONS = [
    # Shared blocker, unchanged since April.
    """
    CREATE OR REPLACE FUNCTION fn_prevent_immutability_violation()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'SECURITY: Audit record is immutable. Operation denied.';
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    """,
    # The hashed part of a row: an explicit, versioned column list (chain_genesis.columns), never
    # the whole row, so adding a column later can't silently change every old row's payload.
    # jsonb's text form is canonical (sorted keys, fixed formatting).
    """
    CREATE OR REPLACE FUNCTION fn_chain_payload(rec jsonb, cols text[])
    RETURNS text LANGUAGE sql IMMUTABLE AS $$
        SELECT coalesce(jsonb_object_agg(key, value), '{}'::jsonb)::text
        FROM jsonb_each(rec) WHERE key = ANY(cols)
    $$;
    """,
    # One SHA-256 over every pre-chain row (chain_seq IS NULL), in primary-key order. Recorded
    # once in chain_genesis; recomputed by fn_verify_chain. Old rows are never updated.
    f"""
    CREATE OR REPLACE FUNCTION fn_chain_legacy_seal(tbl text, cols text[], pk text,
                                                    OUT n bigint, OUT seal text)
    LANGUAGE plpgsql STABLE {DETERMINISTIC} AS $$
    BEGIN
        EXECUTE format(
            'SELECT count(*), encode(sha256(convert_to(%L || E''\\n'' || coalesce(string_agg('
            'fn_chain_payload(to_jsonb(t), $1), E''\\n'' ORDER BY t.%I), ''''), ''UTF8'')), ''hex'') '
            'FROM %I t WHERE t.chain_seq IS NULL', tbl, pk, tbl)
        USING cols INTO n, seal;
    END;
    $$;
    """,
    # BEFORE INSERT on each protected table: link the new row to the previous one.
    f"""
    CREATE OR REPLACE FUNCTION fn_chain_append()
    RETURNS TRIGGER LANGUAGE plpgsql {DETERMINISTIC} AS $$
    DECLARE
        g record;
        last_seq bigint;
        last_hash text;
    BEGIN
        -- Serialise appends per table, so two concurrent inserts can't fork the chain.
        PERFORM pg_advisory_xact_lock(hashtextextended('grc_chain:' || TG_TABLE_NAME, 0));
        SELECT columns, seal_hash INTO g FROM chain_genesis
         WHERE table_name = TG_TABLE_NAME ORDER BY chain_version DESC LIMIT 1;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'SECURITY: no chain genesis for %; run core.migrate', TG_TABLE_NAME;
        END IF;
        EXECUTE format('SELECT chain_seq, row_hash FROM %I WHERE chain_seq IS NOT NULL '
                       'ORDER BY chain_seq DESC LIMIT 1', TG_TABLE_NAME)
            INTO last_seq, last_hash;
        NEW.chain_seq := coalesce(last_seq, 0) + 1;
        NEW.prev_hash := coalesce(last_hash, g.seal_hash);
        NEW.row_hash := encode(sha256(convert_to(
            NEW.prev_hash || E'\\n' || fn_chain_payload(to_jsonb(NEW), g.columns), 'UTF8')), 'hex');
        RETURN NEW;
    END;
    $$;
    """,
    # Recompute the seal, then walk the chain. first_bad_seq: 0 = the sealed pre-chain rows
    # changed; n = chained row n (or a gap where it should be) is wrong.
    f"""
    CREATE OR REPLACE FUNCTION fn_verify_chain(tbl text)
    RETURNS TABLE(intact boolean, first_bad_seq bigint, rows_checked bigint)
    LANGUAGE plpgsql STABLE {DETERMINISTIC} AS $$
    DECLARE
        g record;
        r record;
        legacy record;
        expected_seq bigint := 0;
        expected_prev text;
    BEGIN
        IF NOT tbl = ANY(ARRAY{list(PROTECTED_TABLES)}) THEN
            RAISE EXCEPTION 'not a chained table: %', tbl;
        END IF;
        SELECT * INTO g FROM chain_genesis WHERE table_name = tbl
         ORDER BY chain_version DESC LIMIT 1;
        IF NOT FOUND THEN
            RETURN QUERY SELECT false, 0::bigint, 0::bigint;
            RETURN;
        END IF;
        SELECT * INTO legacy FROM fn_chain_legacy_seal(tbl, g.columns, g.pk_column);
        rows_checked := legacy.n;
        IF legacy.n <> g.legacy_rows OR legacy.seal <> g.seal_hash THEN
            RETURN QUERY SELECT false, 0::bigint, rows_checked;
            RETURN;
        END IF;
        expected_prev := g.seal_hash;
        FOR r IN EXECUTE format(
            'SELECT chain_seq, prev_hash, row_hash, fn_chain_payload(to_jsonb(t), $1) AS payload '
            'FROM %I t WHERE chain_seq IS NOT NULL ORDER BY chain_seq', tbl) USING g.columns
        LOOP
            expected_seq := expected_seq + 1;
            rows_checked := rows_checked + 1;
            IF r.chain_seq <> expected_seq
               OR r.prev_hash IS DISTINCT FROM expected_prev
               OR r.row_hash IS DISTINCT FROM encode(sha256(convert_to(
                      r.prev_hash || E'\\n' || r.payload, 'UTF8')), 'hex') THEN
                RETURN QUERY SELECT false, expected_seq, rows_checked;
                RETURN;
            END IF;
            expected_prev := r.row_hash;
        END LOOP;
        RETURN QUERY SELECT true, NULL::bigint, rows_checked;
    END;
    $$;
    """,
]

GENESIS_TABLE = """
    CREATE TABLE IF NOT EXISTS chain_genesis (
        id            bigserial PRIMARY KEY,
        table_name    text        NOT NULL,
        chain_version integer     NOT NULL,
        columns       text[]      NOT NULL,
        pk_column     text        NOT NULL,
        sealed_at     timestamptz NOT NULL DEFAULT now(),
        legacy_rows   bigint      NOT NULL,
        seal_hash     text        NOT NULL,
        UNIQUE (table_name, chain_version)
    );
"""


def _blockers(table):
    prefix = BLOCKER_PREFIX[table]
    parts = []
    for event, level in (("UPDATE", "ROW"), ("DELETE", "ROW"), ("TRUNCATE", "STATEMENT")):
        name = f"{prefix}_no_{event.lower()}"
        parts.append(f"""
            IF NOT EXISTS (SELECT 1 FROM pg_trigger
                           WHERE tgname = '{name}' AND tgrelid = '{table}'::regclass) THEN
                CREATE TRIGGER {name} BEFORE {event} ON {table}
                FOR EACH {level} EXECUTE FUNCTION fn_prevent_immutability_violation();
            END IF;""")
    return "DO $$ BEGIN" + "".join(parts) + "\nEND $$;"


async def _seal_if_new(conn, table):
    exists = (await conn.execute(text(
        "SELECT 1 FROM chain_genesis WHERE table_name = :t AND chain_version = :v"),
        {"t": table, "v": CHAIN_VERSION})).first()
    if exists:
        return
    cols = [r[0] for r in (await conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND NOT (column_name::text = ANY(:chain)) "
        "ORDER BY ordinal_position"), {"t": table, "chain": list(CHAIN_COLUMNS)})).all()]
    pk = (await conn.execute(text(
        "SELECT a.attname FROM pg_index i JOIN pg_attribute a "
        "ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE i.indrelid = CAST(:t AS regclass) AND i.indisprimary"), {"t": table})).scalar_one()
    n, seal = (await conn.execute(text(
        "SELECT n, seal FROM fn_chain_legacy_seal(:t, :cols, :pk)"),
        {"t": table, "cols": cols, "pk": pk})).one()
    await conn.execute(text(
        "INSERT INTO chain_genesis (table_name, chain_version, columns, pk_column, legacy_rows, seal_hash) "
        "VALUES (:t, :v, :cols, :pk, :n, :seal)"),
        {"t": table, "v": CHAIN_VERSION, "cols": cols, "pk": pk, "n": n, "seal": seal})
    print(f"migrate: sealed {n} pre-chain rows of {table}")


async def migrate(url: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Widen the stagestatus enum for values added after it was first created (TPRM 2.4).
            # create_all() never ALTERs an existing enum; ADD VALUE can't run inside a DO block.
            await conn.execute(text("ALTER TYPE stagestatus ADD VALUE IF NOT EXISTS 'NOT_APPLICABLE';"))

            await conn.execute(text(GENESIS_TABLE))
            for table in PROTECTED_TABLES:
                await conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS chain_seq bigint, "
                    f"ADD COLUMN IF NOT EXISTS prev_hash text, ADD COLUMN IF NOT EXISTS row_hash text;"))
                await conn.execute(text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_chain_seq "
                    f"ON {table} (chain_seq) WHERE chain_seq IS NOT NULL;"))
            for fn in FUNCTIONS:
                await conn.execute(text(fn))

            # Seal the existing rows before the chain trigger exists, so none is chained twice.
            for table in PROTECTED_TABLES:
                await _seal_if_new(conn, table)
            for table in (*PROTECTED_TABLES, "chain_genesis"):
                await conn.execute(text(_blockers(table)))
            for table in PROTECTED_TABLES:
                await conn.execute(text(f"""
                    DO $$ BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_chain_append'
                                       AND tgrelid = '{table}'::regclass) THEN
                            CREATE TRIGGER trg_chain_append BEFORE INSERT ON {table}
                            FOR EACH ROW EXECUTE FUNCTION fn_chain_append();
                        END IF;
                    END $$;"""))

            # Least privilege, re-applied on every run so a new table never inherits more.
            protected = ", ".join(PROTECTED_TABLES)
            for stmt in (
                f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}",
                f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}",
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}",
                f"REVOKE UPDATE, DELETE ON {protected} FROM {APP_ROLE}",
                f"REVOKE INSERT, UPDATE, DELETE ON chain_genesis FROM {APP_ROLE}",
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}",
            ):
                await conn.execute(text(stmt))
    finally:
        await engine.dispose()


def main() -> int:
    url = os.environ.get("MIGRATE_DATABASE_URL")
    if not url:
        print("migrate: MIGRATE_DATABASE_URL is not set", file=sys.stderr)
        return 1
    try:
        asyncio.run(migrate(url))
    except Exception as e:
        # Fail closed: the backend's depends_on keeps it down until this succeeds.
        print(f"migrate: FAILED, nothing applied ({type(e).__name__}): {e}", file=sys.stderr)
        return 1
    print("migrate: schema, protections, audit chain and grants are in place")
    return 0


if __name__ == "__main__":
    sys.exit(main())
