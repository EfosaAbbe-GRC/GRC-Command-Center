import sqlite3
import os
import datetime
from core.logger import logger

class AuditLogger:
    def __init__(self, db_path: str = None):
        if db_path is None:
            from core.config import settings
            self.db_path = settings.DATABASE_PATH
        else:
            self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes the SQLite database and creates the audit_logs table if it doesn't exist."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=5000")
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id TEXT,
                        timestamp TEXT,
                        query TEXT,
                        response TEXT,
                        context TEXT,
                        sources TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS evidence_chain (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        file_hash TEXT NOT NULL,
                        file_size_bytes INTEGER NOT NULL,
                        source_path TEXT NOT NULL,
                        ingested_by TEXT DEFAULT 'system',
                        status TEXT DEFAULT 'ACTIVE'
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        hashed_password TEXT NOT NULL,
                        role TEXT NOT NULL,
                        status TEXT DEFAULT 'enabled',
                        last_login TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT,
                        password_changed_at TEXT,
                        must_change_password INTEGER DEFAULT 0
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS refresh_tokens (
                        jti TEXT PRIMARY KEY,
                        user_id INTEGER,
                        expires_at TEXT NOT NULL,
                        revoked INTEGER DEFAULT 0
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS security_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        user TEXT,
                        ip_address TEXT,
                        detail TEXT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS policies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        required_role TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        policy_version INTEGER DEFAULT 1,
                        source_doc TEXT,
                        created_by TEXT,
                        modified_by TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT
                    )
                """)

                # Enforce append-only: prevent UPDATE and DELETE on audit_logs
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS prevent_audit_update
                    BEFORE UPDATE ON audit_logs
                    BEGIN
                        SELECT RAISE(ABORT, 'SECURITY: Audit logs are immutable. UPDATE operations are prohibited.');
                    END
                """)
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
                    BEFORE DELETE ON audit_logs
                    BEGIN
                        SELECT RAISE(ABORT, 'SECURITY: Audit logs are immutable. DELETE operations are prohibited.');
                    END
                """)
                
                # Same for evidence chain
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS prevent_evidence_update
                    BEFORE UPDATE ON evidence_chain
                    BEGIN
                        SELECT RAISE(ABORT, 'SECURITY: Evidence records are immutable. UPDATE operations are prohibited.');
                    END
                """)
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS prevent_evidence_delete
                    BEFORE DELETE ON evidence_chain
                    BEGIN
                        SELECT RAISE(ABORT, 'SECURITY: Evidence records are immutable. DELETE operations are prohibited.');
                    END
                """)
                conn.commit()
            logger.info("Audit database initialized", path=self.db_path)
        except Exception as e:
            logger.error("Failed to initialize audit database", error=str(e))

    def log_interaction(self, request_id: str, query: str, response: str, context: str, sources: list):
        """Logs a single RAG interaction to the database."""
        try:
            timestamp = datetime.datetime.now().isoformat()
            sources_str = ", ".join(sources) if sources else ""
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=5000")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_logs (request_id, timestamp, query, response, context, sources)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (request_id, timestamp, query, response, context, sources_str))
                conn.commit()
            logger.info("Audit log entry created", request_id=request_id)
        except Exception as e:
            logger.error("Audit logging failed", request_id=request_id, error=str(e))

    def log_evidence(self, filename: str, file_hash: str, file_size: int, source_path: str, ingested_by: str = "system"):
        """Record chain-of-custody entry for an ingested document."""
        try:
            timestamp = datetime.datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=5000")
                cursor = conn.cursor()
                
                # Check if this exact file+hash already exists (avoid duplicates)
                cursor.execute(
                    "SELECT id FROM evidence_chain WHERE filename = ? AND file_hash = ?",
                    (filename, file_hash)
                )
                if cursor.fetchone():
                    logger.info("Evidence: File already recorded", filename=filename, hash=file_hash[:16])
                    return
                
                cursor.execute("""
                    INSERT INTO evidence_chain (timestamp, filename, file_hash, file_size_bytes, source_path, ingested_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (timestamp, filename, file_hash, file_size, source_path, ingested_by))
                conn.commit()
            logger.info("Evidence: Chain-of-custody recorded", filename=filename, hash=file_hash[:16])
        except Exception as e:
            logger.error("Evidence logging failed", filename=filename, error=str(e))

    def get_evidence_records(self):
        """Retrieve all evidence chain records."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT filename, file_hash, file_size_bytes, timestamp, ingested_by, status FROM evidence_chain ORDER BY timestamp DESC")
                rows = cursor.fetchall()
                return [
                    {
                        "filename": r[0],
                        "file_hash": r[1],
                        "file_size": r[2],
                        "timestamp": r[3],
                        "ingested_by": r[4],
                        "status": r[5]
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error("Evidence retrieval failed", error=str(e))
            return []

    def log_security_event(self, event_type: str, user: str = "anonymous", ip_address: str = "unknown", detail: str = ""):
        """Record critical security events (logins, unauthorized access) for compliance audit."""
        try:
            timestamp = datetime.datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("INSERT INTO security_events (timestamp, event_type, user, ip_address, detail) VALUES (?, ?, ?, ?, ?)",
                             (timestamp, event_type, user, ip_address, detail))
                conn.commit()
            logger.info("Security logic: event recorded", type=event_type, user=user)
        except Exception as e:
            logger.error("Security logging failed", error=str(e))

    def get_security_events(self, limit: int = 50, offset: int = 0, event_type: str = None, user: str = None):
        """Retrieve security events with filtering and pagination for admin audit layer."""
        try:
            query = "SELECT id, timestamp, event_type, user, ip_address, detail FROM security_events"
            params = []
            where_clauses = []

            if event_type:
                where_clauses.append("event_type = ?")
                params.append(event_type)
            if user:
                where_clauses.append("user LIKE ?")
                params.append(f"%{user}%")

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "timestamp": r[1],
                        "event_type": r[2],
                        "user": r[3],
                        "ip_address": r[4],
                        "detail": r[5]
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error("Security audit retrieval failed", error=str(e))
            return []

    def get_user_by_username(self, username: str):
        """Fetch a single user record for authentication."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                if row:
                    # Return as dict for clean handling in auth.py
                    return {
                        "id": row[0],
                        "username": row[1],
                        "hashed_password": row[2],
                        "role": row[3],
                        "status": row[4],
                        "last_login": row[5],
                        "created_at": row[6],
                        "updated_at": row[7],
                        "password_changed_at": row[8],
                        "must_change_password": bool(row[9])
                    }
                return None
        except Exception as e:
            logger.error("User lookup failed", username=username, error=str(e))
            return None

    def get_user_by_id(self, user_id: int):
        """Fetch a single user record by numeric ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "username": row[1],
                        "hashed_password": row[2],
                        "role": row[3],
                        "status": row[4],
                        "last_login": row[5],
                        "created_at": row[6],
                        "updated_at": row[7],
                        "password_changed_at": row[8],
                        "must_change_password": bool(row[9])
                    }
                return None
        except Exception as e:
            logger.error("User lookup failed", user_id=user_id, error=str(e))
            return None

    def create_user(self, username: str, hashed_password: str, role: str):
        """Creates a new user record in the identity store."""
        try:
            timestamp = datetime.datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    INSERT INTO users (username, hashed_password, role, created_at)
                    VALUES (?, ?, ?, ?)
                """, (username, hashed_password, role, timestamp))
                conn.commit()
            logger.info("Security logic: user created", username=username, role=role)
            return True
        except Exception as e:
            logger.error("User creation failed", username=username, error=str(e))
            return False

    def update_password(self, user_id: int, hashed_password: str):
        """Persistent update for user credentials with password_changed_at update."""
        try:
            timestamp = datetime.datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    UPDATE users 
                    SET hashed_password = ?, password_changed_at = ?, must_change_password = 0, updated_at = ?
                    WHERE id = ?
                """, (hashed_password, timestamp, timestamp, user_id))
                conn.commit()
            logger.info("Security logic: password updated", user_id=user_id)
            return True
        except Exception as e:
            logger.error("Password update failed", user_id=user_id, error=str(e))
            return False

    def set_must_change_password(self, user_id: int, flag: bool):
        """Administratively force/clear password change requirement."""
        try:
            val = 1 if flag else 0
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("UPDATE users SET must_change_password = ? WHERE id = ?", (val, user_id))
                conn.commit()
            logger.info("Security logic: user required reset state changed", user_id=user_id, flag=flag)
            return True
        except Exception as e:
            logger.error("Forced reset update failed", user_id=user_id, error=str(e))
            return False

    def update_last_login(self, username: str):
        """Updates the last_login timestamp on successful authentication."""
        try:
            timestamp = datetime.datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("UPDATE users SET last_login = ? WHERE username = ?", (timestamp, username))
                conn.commit()
        except Exception as e:
            logger.error("Failed to update last_login", username=username, error=str(e))

    def create_refresh_token(self, jti: str, user_id: int, expires_at: datetime.datetime):
        """Record a new refresh token jti in the database."""
        try:
            expires_str = expires_at.isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("INSERT INTO refresh_tokens (jti, user_id, expires_at) VALUES (?, ?, ?)",
                             (jti, user_id, expires_str))
                conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to create refresh token", jti=jti, error=str(e))
            return False

    def get_refresh_token(self, jti: str):
        """Check if a refresh token jti exists and is not revoked."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, expires_at, revoked FROM refresh_tokens WHERE jti = ?", (jti,))
                row = cursor.fetchone()
                if row:
                    return {"user_id": row[0], "expires_at": row[1], "revoked": bool(row[2])}
                return None
        except Exception as e:
            logger.error("Refresh token lookup failed", jti=jti, error=str(e))
            return None

    def revoke_refresh_token(self, jti: str):
        """Mark a refresh token as revoked (One-time-use rotation or logout)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("UPDATE refresh_tokens SET revoked = 1 WHERE jti = ?", (jti,))
                conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to revoke refresh token", jti=jti, error=str(e))
            return False

    # --- POLICY ENGINE METHODS (IAM-09) ---

    def create_policy(self, name: str, description: str, required_role: str, created_by: str, source_doc: str = None):
        """Register a new dynamic access policy."""
        try:
            timestamp = datetime.datetime.now().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    INSERT INTO policies (name, description, required_role, created_by, created_at, source_doc)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, description, required_role, created_by, timestamp, source_doc))
                conn.commit()
            logger.info("Policy Engine: Policy created", name=name, role=required_role)
            return True
        except Exception as e:
            logger.error("Policy creation failed", name=name, error=str(e))
            return False

    def update_policy(self, policy_id: int, required_role: str, is_active: bool, modified_by: str, source_doc: str = None):
        """Update an existing policy with version increment."""
        try:
            timestamp = datetime.datetime.now().isoformat()
            active_val = 1 if is_active else 0
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    UPDATE policies 
                    SET required_role = ?, is_active = ?, modified_by = ?, 
                        policy_version = policy_version + 1, updated_at = ?, source_doc = ?
                    WHERE id = ?
                """, (required_role, active_val, modified_by, timestamp, source_doc, policy_id))
                conn.commit()
            logger.info("Policy Engine: Policy updated", id=policy_id, role=required_role)
            return True
        except Exception as e:
            logger.error("Policy update failed", id=policy_id, error=str(e))
            return False

    def get_policy(self, name: str):
        """Fetch a specific policy by its machine-name identifier."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM policies WHERE name = ?", (name,))
                row = cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "required_role": row[3],
                        "is_active": bool(row[4]),
                        "version": row[5],
                        "source_doc": row[6]
                    }
                return None
        except Exception as e:
            logger.error("Policy lookup failed", name=name, error=str(e))
            return None

    def list_policies(self):
        """Retrieve all defined access policies."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM policies ORDER BY name ASC")
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "name": r[1],
                        "description": r[2],
                        "required_role": r[3],
                        "is_active": bool(r[4]),
                        "version": r[5],
                        "source_doc": r[6],
                        "created_by": r[7],
                        "modified_by": r[8],
                        "created_at": r[9],
                        "updated_at": r[10]
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error("Policy listing failed", error=str(e))
            return []

# Singleton instance for the app
audit_logger = AuditLogger()
