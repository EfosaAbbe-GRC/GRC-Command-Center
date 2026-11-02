#!/bin/sh
# Least-privilege database roles (docs/refactors/Secrets_DB_Privilege_refactor.md §5.1).
#
#   grc_admin   superuser (the Postgres bootstrap role). Nothing running uses it: break-glass only.
#   grc_owner   owns every schema object; not a superuser. Used only by the one-shot db-migrate.
#   grc_app     the backend. Can add and read evidence, never alter, delete or un-protect it.
#   grc_backup  pg_read_all_data and nothing else. Used by db-backup.
#
# Runs by itself on a FRESH volume (mounted into /docker-entrypoint-initdb.d/). On an EXISTING
# volume, run it once by hand:  docker exec <db container> sh /docker-entrypoint-initdb.d/10-roles.sh
# Idempotent. Passwords come from the container's environment through psql's \getenv, so they
# never appear in a process argument or in output.

for v in POSTGRES_PASSWORD GRC_OWNER_DB_PASSWORD GRC_APP_DB_PASSWORD GRC_BACKUP_DB_PASSWORD; do
    eval "val=\${$v:-}"
    if [ -z "$val" ]; then echo "10-roles.sh: $v is not set; refusing" >&2; exit 1; fi
done

psql -v ON_ERROR_STOP=1 -q -X --username "${POSTGRES_USER:-grc_admin}" --dbname "$POSTGRES_DB" <<'SQL'
\getenv admin_pw POSTGRES_PASSWORD
\getenv owner_pw GRC_OWNER_DB_PASSWORD
\getenv app_pw GRC_APP_DB_PASSWORD
\getenv backup_pw GRC_BACKUP_DB_PASSWORD

SELECT format('CREATE ROLE %I', r) FROM unnest(ARRAY['grc_owner', 'grc_app', 'grc_backup']) AS r
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) \gexec

ALTER ROLE grc_owner  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION PASSWORD :'owner_pw';
ALTER ROLE grc_app    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION PASSWORD :'app_pw';
ALTER ROLE grc_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION PASSWORD :'backup_pw';
ALTER ROLE CURRENT_USER PASSWORD :'admin_pw';
GRANT pg_read_all_data TO grc_backup;

-- The database owner owns schema public (PG 15+: pg_database_owner), so grc_owner can create in it.
SELECT format('ALTER DATABASE %I OWNER TO grc_owner', current_database()) \gexec

-- Hand every existing object to grc_owner. Tables first: their indexes and linked sequences follow.
SELECT format('ALTER %s %I.%I OWNER TO grc_owner',
              CASE c.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW' ELSE 'TABLE' END,
              n.nspname, c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm')
   AND c.relowner <> 'grc_owner'::regrole \gexec
SELECT format('ALTER SEQUENCE %I.%I OWNER TO grc_owner', n.nspname, c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind = 'S' AND c.relowner <> 'grc_owner'::regrole \gexec
SELECT format('ALTER FUNCTION %s OWNER TO grc_owner', p.oid::regprocedure)
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'public' AND p.proowner <> 'grc_owner'::regrole \gexec
SELECT format('ALTER TYPE %I.%I OWNER TO grc_owner', n.nspname, t.typname)
  FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
 WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd') AND t.typowner <> 'grc_owner'::regrole \gexec
SQL
echo "10-roles.sh: roles and ownership in place"
