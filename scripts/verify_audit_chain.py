"""Verify the tamper-evident audit chain and print each table's head hash (admin, on the host).

    python scripts/verify_audit_chain.py              # dev stack
    python scripts/verify_audit_chain.py --test       # isolated test stack

Exit 0 if every protected table verifies, 1 otherwise. /api/v1/readiness only says intact or
broken; this script also names the first bad sequence number and prints the head hashes.

Record the head hashes somewhere the database can't touch (a private note, a signed commit to a
private repo). Someone with host access could recompute the whole chain after an edit; a head
hash recorded earlier is what still catches that (Secrets_DB_Privilege_refactor.md §8, T4).
"""
import argparse
import subprocess
import sys

# Must equal backend/core/security_config.PROTECTED_TABLES (guarded by tests/test_risk_scoring.py).
TABLES = ["audit_logs", "evidence_chain", "security_events", "risk_acceptances",
          "stage_evidence_links", "risk_events"]

SQL = """
SELECT v.intact, coalesce(v.first_bad_seq::text, '-'), v.rows_checked,
       coalesce((SELECT max(chain_seq) FROM {t})::text, '0'),
       coalesce((SELECT row_hash FROM {t} WHERE chain_seq IS NOT NULL ORDER BY chain_seq DESC LIMIT 1),
                (SELECT seal_hash FROM chain_genesis WHERE table_name = '{t}'
                 ORDER BY chain_version DESC LIMIT 1), '-')
FROM fn_verify_chain('{t}') v;
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--test", action="store_true", help="check the test stack instead of dev")
    args = ap.parse_args()
    container, db = ("grc-db-pg-test", "grc_audit_test") if args.test else ("grc-db-pg", "grc_audit")

    # As grc_app over the container's local socket: the same view the backend has.
    sql = "".join(SQL.format(t=t) for t in TABLES)
    r = subprocess.run(["docker", "exec", "-i", container, "psql", "-U", "grc_app", "-d", db,
                        "-v", "ON_ERROR_STOP=1", "-At", "-q", "-F", "|"],
                       input=sql, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"verification query failed on {container}:\n{r.stderr.strip()}", file=sys.stderr)
        return 1

    print(f"Audit chain on {container}/{db}")
    print(f"{'table':<22} {'status':<8} {'bad seq':>7} {'rows':>7} {'head seq':>8}  head hash")
    all_ok = True
    for table, line in zip(TABLES, r.stdout.strip().splitlines()):
        intact, bad, rows, head_seq, head = line.split("|")
        ok = intact == "t"
        all_ok &= ok
        print(f"{table:<22} {'intact' if ok else 'BROKEN':<8} {bad:>7} {rows:>7} {head_seq:>8}  {head}")
    print("ALL INTACT" if all_ok else "TAMPERING OR DAMAGE DETECTED: see 'bad seq' (0 = sealed pre-chain rows)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
