from core.database import audit_logger

def force_reset():
    user = audit_logger.get_user_by_username("admin")
    if user:
        audit_logger.set_must_change_password(user["id"], True)
        print(f"✅ Admin account (ID: {user['id']}) forced into reset state for verification.")

if __name__ == "__main__":
    force_reset()
