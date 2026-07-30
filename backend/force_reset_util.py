"""
Admin forced-reset toggle utility.

    python force_reset_util.py            # LOCK   (set must_change_password=True)
    python force_reset_util.py --unlock   # UNLOCK (clear the flag)

Run inside the backend container (DATABASE_URL points to the compose `db` host):

    docker exec grc-backend python force_reset_util.py --unlock

Previously this only LOCKED admin with no paired unlock — a one-way footgun that
could strand the account (and 403-cascade the whole test suite). `--unlock` is
the escape hatch. The default is still LOCK for backward compatibility.
"""
import sys

from core.database import audit_logger


def set_reset(flag: bool):
    user = audit_logger.get_user_by_username("admin")
    if not user:
        print("⚠️  admin account not found")
        return
    audit_logger.set_must_change_password(user["id"], flag)
    state = "LOCKED (forced-reset set)" if flag else "UNLOCKED (forced-reset cleared)"
    print(f"✅ Admin account (ID: {user['id']}) {state}.")


if __name__ == "__main__":
    unlock = "--unlock" in sys.argv
    set_reset(flag=not unlock)
