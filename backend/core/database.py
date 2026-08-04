"""
GRC Command Center — PostgreSQL 16 Database Core
Async-first architecture using SQLAlchemy 2.0 + asyncpg.
Enforces SECURITY DEFINER immutability on audit_logs and evidence_chain.
"""
import os
import datetime
import asyncio
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, text, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from core.logger import logger
from core.config import settings
from core.models import Base, AuditLog, EvidenceChain, User, RefreshToken, SecurityEvent, Policy

# ─── Engine Setup ────────────────────────────────────────────────────────────
DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ─── FastAPI Dependency ──────────────────────────────────────────────────────
async def get_db():
    """Yields an AsyncSession for request-scoped dependency injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ─── Helper: run async from sync context ──────────────────────────────────────
def _run_async(coro):
    """Bridge utility: run an async coroutine from a synchronous call site.
    Always uses a fresh event loop in a dedicated thread to avoid
    'attached to a different loop' errors with asyncpg connection pooling."""
    import concurrent.futures

    def _runner():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_runner)
        return future.result(timeout=30)


def _naive_utcnow() -> datetime.datetime:
    """UTC 'now' as a NAIVE datetime.

    The User/Policy timestamp columns are DateTime == TIMESTAMP WITHOUT TIME
    ZONE. asyncpg raises DataError ('can't subtract offset-naive and
    offset-aware datetimes') if a tz-aware value is bound to such a column,
    which silently failed update_last_login and 500'd change-password
    (breaking forced-reset recovery). All writes to those columns must be naive.
    """
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class AuditLogger:
    """
    PostgreSQL-backed audit logger with SECURITY DEFINER immutability.
    Exposes both async methods (for use with Depends(get_db)) and
    sync wrappers (for middleware, background tasks, and lifespan seeding).
    """

    # ─── Schema Initialization ────────────────────────────────────────────────

    async def init_db(self):
        """Creates all tables and installs PL/pgSQL immutability triggers."""
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

                logger.info("Database: Installing SECURITY DEFINER immutability triggers...")

                # 1. Shared protection function
                await conn.execute(text("""
                    CREATE OR REPLACE FUNCTION fn_prevent_immutability_violation()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        RAISE EXCEPTION 'SECURITY: Audit record is immutable. Operation denied.';
                    END;
                    $$ LANGUAGE plpgsql SECURITY DEFINER;
                """))

                # 2. Audit logs — block UPDATE and DELETE
                await conn.execute(text("""
                    DO $$ BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_no_update') THEN
                            CREATE TRIGGER trg_audit_no_update BEFORE UPDATE ON audit_logs
                            FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_no_delete') THEN
                            CREATE TRIGGER trg_audit_no_delete BEFORE DELETE ON audit_logs
                            FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_no_truncate') THEN
                            CREATE TRIGGER trg_audit_no_truncate BEFORE TRUNCATE ON audit_logs
                            FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_immutability_violation();
                        END IF;
                    END $$;
                """))

                # 3. Evidence chain — block UPDATE and DELETE
                await conn.execute(text("""
                    DO $$ BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_evidence_no_update') THEN
                            CREATE TRIGGER trg_evidence_no_update BEFORE UPDATE ON evidence_chain
                            FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_evidence_no_delete') THEN
                            CREATE TRIGGER trg_evidence_no_delete BEFORE DELETE ON evidence_chain
                            FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_evidence_no_truncate') THEN
                            CREATE TRIGGER trg_evidence_no_truncate BEFORE TRUNCATE ON evidence_chain
                            FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_immutability_violation();
                        END IF;
                    END $$;
                """))

                # 4. Risk acceptances (TPRM) — block UPDATE and DELETE.
                # Reuses fn_prevent_immutability_violation(); guarded so it is a
                # no-op until the TPRM models have been registered/created.
                await conn.execute(text("""
                    DO $$ BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.tables
                                   WHERE table_name = 'risk_acceptances') THEN
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_risk_acc_no_update') THEN
                                CREATE TRIGGER trg_risk_acc_no_update BEFORE UPDATE ON risk_acceptances
                                FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_risk_acc_no_delete') THEN
                                CREATE TRIGGER trg_risk_acc_no_delete BEFORE DELETE ON risk_acceptances
                                FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_risk_acc_no_truncate') THEN
                                CREATE TRIGGER trg_risk_acc_no_truncate BEFORE TRUNCATE ON risk_acceptances
                                FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                        END IF;
                    END $$;
                """))

                # 5. Stage evidence links (TPRM) — block UPDATE and DELETE/TRUNCATE.
                # Reuses fn_prevent_immutability_violation(); guarded so it is a
                # no-op until the TPRM models have been registered/created.
                await conn.execute(text("""
                    DO $$ BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.tables
                                   WHERE table_name = 'stage_evidence_links') THEN
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_stage_evidence_no_update') THEN
                                CREATE TRIGGER trg_stage_evidence_no_update BEFORE UPDATE ON stage_evidence_links
                                FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_stage_evidence_no_delete') THEN
                                CREATE TRIGGER trg_stage_evidence_no_delete BEFORE DELETE ON stage_evidence_links
                                FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_stage_evidence_no_truncate') THEN
                                CREATE TRIGGER trg_stage_evidence_no_truncate BEFORE TRUNCATE ON stage_evidence_links
                                FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                        END IF;
                    END $$;
                """))

                # 6. Widen the stagestatus enum for values added after this type was
                # first created (TPRM 2.4: NOT_APPLICABLE). create_all() only creates
                # missing enum types, it never ALTERs an existing one to add a new
                # label -- and ALTER TYPE ... ADD VALUE cannot run inside a DO block
                # or function body, so this must stay a plain top-level statement.
                await conn.execute(text(
                    "ALTER TYPE stagestatus ADD VALUE IF NOT EXISTS 'NOT_APPLICABLE';"
                ))

            logger.info("Database: PostgreSQL initialization and hardening complete.")
        except Exception as e:
            logger.error("Database: Initialization failed", error=str(e))
            raise

    # ─── Audit Logging ────────────────────────────────────────────────────────

    async def _log_interaction_async(self, request_id: str, query: str, response: str, context: str, sources: list):
        """Async: persist a RAG interaction to the audit trail."""
        try:
            async with AsyncSessionLocal() as session:
                sources_str = ", ".join(sources) if sources else ""
                log = AuditLog(
                    request_id=request_id,
                    query=query,
                    response=response,
                    context=context,
                    sources=sources_str,
                )
                session.add(log)
                await session.commit()
            logger.info("Audit log entry created", request_id=request_id)
        except Exception as e:
            logger.error("Audit logging failed", request_id=request_id, error=str(e))

    def log_interaction(self, request_id: str, query: str, response: str, context: str, sources: list):
        """Sync bridge: called from BackgroundTasks."""
        _run_async(self._log_interaction_async(request_id, query, response, context, sources))

    # ─── Evidence Chain ───────────────────────────────────────────────────────

    async def _log_evidence_async(self, filename: str, file_hash: str, file_size: int, source_path: str, ingested_by: str = "system") -> int:
        async with AsyncSessionLocal() as session:
            # Dedup check
            result = await session.execute(
                select(EvidenceChain).where(
                    EvidenceChain.filename == filename,
                    EvidenceChain.file_hash == file_hash,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                logger.info("Evidence: File already recorded", filename=filename, hash=file_hash[:16])
                return existing.id

            entry = EvidenceChain(
                filename=filename,
                file_hash=file_hash,
                file_size_bytes=file_size,
                source_path=source_path,
                ingested_by=ingested_by,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
        logger.info("Evidence: Chain-of-custody recorded", filename=filename, hash=file_hash[:16])
        return entry.id

    def log_evidence(self, filename: str, file_hash: str, file_size: int, source_path: str, ingested_by: str = "system") -> int:
        """Sync bridge: called from RAG ingestion loop and TPRM stage evidence upload.
        Returns the evidence_chain row id (new or, on dedup hit, existing) so callers
        can link a foreign-key reference to it."""
        return _run_async(self._log_evidence_async(filename, file_hash, file_size, source_path, ingested_by))

    async def _get_evidence_records_async(self):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(EvidenceChain).order_by(EvidenceChain.timestamp.desc())
                )
                rows = result.scalars().all()
                return [
                    {
                        "filename": r.filename,
                        "file_hash": r.file_hash,
                        "file_size": r.file_size_bytes,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                        "ingested_by": r.ingested_by,
                        "status": r.status,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error("Evidence retrieval failed", error=str(e))
            return []

    def get_evidence_records(self):
        return _run_async(self._get_evidence_records_async())

    # ─── User Management ──────────────────────────────────────────────────────

    async def _get_user_by_username_async(self, username: str):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(User).where(User.username == username))
                user = result.scalar_one_or_none()
                if user:
                    return {
                        "id": user.id,
                        "username": user.username,
                        "hashed_password": user.hashed_password,
                        "role": user.role,
                        "status": user.status,
                        "last_login": user.last_login.isoformat() if user.last_login else None,
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                        "password_changed_at": user.password_changed_at.isoformat() if user.password_changed_at else None,
                        "must_change_password": user.must_change_password,
                    }
                return None
        except Exception as e:
            logger.error("User lookup failed", username=username, error=str(e))
            return None

    def get_user_by_username(self, username: str):
        return _run_async(self._get_user_by_username_async(username))

    async def _get_user_by_id_async(self, user_id: int):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user:
                    return {
                        "id": user.id,
                        "username": user.username,
                        "hashed_password": user.hashed_password,
                        "role": user.role,
                        "status": user.status,
                        "last_login": user.last_login.isoformat() if user.last_login else None,
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                        "password_changed_at": user.password_changed_at.isoformat() if user.password_changed_at else None,
                        "must_change_password": user.must_change_password,
                    }
                return None
        except Exception as e:
            logger.error("User lookup failed", user_id=user_id, error=str(e))
            return None

    def get_user_by_id(self, user_id: int):
        return _run_async(self._get_user_by_id_async(user_id))

    async def _create_user_async(self, username: str, hashed_password: str, role: str):
        try:
            async with AsyncSessionLocal() as session:
                user = User(username=username, hashed_password=hashed_password, role=role)
                session.add(user)
                await session.commit()
            logger.info("Security logic: user created", username=username, role=role)
            return True
        except Exception as e:
            logger.error("User creation failed", username=username, error=str(e))
            return False

    def create_user(self, username: str, hashed_password: str, role: str):
        return _run_async(self._create_user_async(username, hashed_password, role))

    async def _update_password_async(self, user_id: int, hashed_password: str):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    return False
                user.hashed_password = hashed_password
                user.password_changed_at = _naive_utcnow()
                user.must_change_password = False
                user.updated_at = _naive_utcnow()
                await session.commit()
            logger.info("Security logic: password updated", user_id=user_id)
            return True
        except Exception as e:
            logger.error("Password update failed", user_id=user_id, error=str(e))
            return False

    def update_password(self, user_id: int, hashed_password: str):
        return _run_async(self._update_password_async(user_id, hashed_password))

    async def _set_must_change_password_async(self, user_id: int, flag: bool):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    return False
                user.must_change_password = flag
                await session.commit()
            logger.info("Security logic: user required reset state changed", user_id=user_id, flag=flag)
            return True
        except Exception as e:
            logger.error("Forced reset update failed", user_id=user_id, error=str(e))
            return False

    def set_must_change_password(self, user_id: int, flag: bool):
        return _run_async(self._set_must_change_password_async(user_id, flag))

    async def _update_last_login_async(self, username: str):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(User).where(User.username == username))
                user = result.scalar_one_or_none()
                if user:
                    user.last_login = _naive_utcnow()
                    await session.commit()
        except Exception as e:
            logger.error("Failed to update last_login", username=username, error=str(e))

    def update_last_login(self, username: str):
        _run_async(self._update_last_login_async(username))

    # ─── Refresh Tokens ───────────────────────────────────────────────────────

    async def _create_refresh_token_async(self, jti: str, user_id: int, expires_at: datetime.datetime):
        try:
            async with AsyncSessionLocal() as session:
                token = RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at)
                session.add(token)
                await session.commit()
            return True
        except Exception as e:
            logger.error("Failed to create refresh token", jti=jti, error=str(e))
            return False

    def create_refresh_token(self, jti: str, user_id: int, expires_at: datetime.datetime):
        return _run_async(self._create_refresh_token_async(jti, user_id, expires_at))

    async def _get_refresh_token_async(self, jti: str):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(RefreshToken).where(RefreshToken.jti == jti))
                token = result.scalar_one_or_none()
                if token:
                    return {
                        "user_id": token.user_id,
                        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                        "revoked": token.revoked,
                    }
                return None
        except Exception as e:
            logger.error("Refresh token lookup failed", jti=jti, error=str(e))
            return None

    def get_refresh_token(self, jti: str):
        return _run_async(self._get_refresh_token_async(jti))

    async def _revoke_refresh_token_async(self, jti: str):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(RefreshToken).where(RefreshToken.jti == jti))
                token = result.scalar_one_or_none()
                if token:
                    token.revoked = True
                    await session.commit()
            return True
        except Exception as e:
            logger.error("Failed to revoke refresh token", jti=jti, error=str(e))
            return False

    def revoke_refresh_token(self, jti: str):
        return _run_async(self._revoke_refresh_token_async(jti))

    # ─── Security Events ──────────────────────────────────────────────────────

    async def _log_security_event_async(self, event_type: str, user: str = "anonymous", ip_address: str = "unknown", detail: str = ""):
        try:
            async with AsyncSessionLocal() as session:
                event = SecurityEvent(
                    event_type=event_type,
                    user=user,
                    ip_address=ip_address,
                    detail=detail,
                )
                session.add(event)
                await session.commit()
            logger.info("Security logic: event recorded", type=event_type, user=user)
        except Exception as e:
            logger.error("Security logging failed", error=str(e))

    def log_security_event(self, event_type: str, user: str = "anonymous", ip_address: str = "unknown", detail: str = ""):
        _run_async(self._log_security_event_async(event_type, user, ip_address, detail))

    async def _get_security_events_async(self, limit: int = 50, offset: int = 0, event_type: str = None, user: str = None):
        try:
            async with AsyncSessionLocal() as session:
                query = select(SecurityEvent)
                if event_type:
                    query = query.where(SecurityEvent.event_type == event_type)
                if user:
                    query = query.where(SecurityEvent.user.contains(user))
                query = query.order_by(SecurityEvent.timestamp.desc()).offset(offset).limit(limit)

                result = await session.execute(query)
                rows = result.scalars().all()
                return [
                    {
                        "id": r.id,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                        "event_type": r.event_type,
                        "user": r.user,
                        "ip_address": r.ip_address,
                        "detail": r.detail,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error("Security audit retrieval failed", error=str(e))
            return []

    def get_security_events(self, limit: int = 50, offset: int = 0, event_type: str = None, user: str = None):
        return _run_async(self._get_security_events_async(limit, offset, event_type, user))

    # ─── Policy Engine (IAM-09) ───────────────────────────────────────────────

    async def _create_policy_async(self, name: str, description: str, required_role: str, created_by: str, source_doc: str = None):
        try:
            async with AsyncSessionLocal() as session:
                policy = Policy(
                    name=name,
                    description=description,
                    required_role=required_role,
                    created_by=created_by,
                    source_doc=source_doc,
                )
                session.add(policy)
                await session.commit()
            logger.info("Policy Engine: Policy created", name=name, role=required_role)
            return True
        except Exception as e:
            logger.error("Policy creation failed", name=name, error=str(e))
            return False

    def create_policy(self, name: str, description: str, required_role: str, created_by: str, source_doc: str = None):
        return _run_async(self._create_policy_async(name, description, required_role, created_by, source_doc))

    async def _update_policy_async(self, policy_id: int, required_role: str, is_active: bool, modified_by: str, source_doc: str = None):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Policy).where(Policy.id == policy_id))
                policy = result.scalar_one_or_none()
                if not policy:
                    return False
                policy.required_role = required_role
                policy.is_active = is_active
                policy.modified_by = modified_by
                policy.source_doc = source_doc
                policy.policy_version = policy.policy_version + 1
                policy.updated_at = _naive_utcnow()
                await session.commit()
            logger.info("Policy Engine: Policy updated", id=policy_id, role=required_role)
            return True
        except Exception as e:
            logger.error("Policy update failed", id=policy_id, error=str(e))
            return False

    def update_policy(self, policy_id: int, required_role: str, is_active: bool, modified_by: str, source_doc: str = None):
        return _run_async(self._update_policy_async(policy_id, required_role, is_active, modified_by, source_doc))

    async def _get_policy_async(self, name: str):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Policy).where(Policy.name == name))
                policy = result.scalar_one_or_none()
                if policy:
                    return {
                        "id": policy.id,
                        "name": policy.name,
                        "description": policy.description,
                        "required_role": policy.required_role,
                        "is_active": policy.is_active,
                        "version": policy.policy_version,
                        "source_doc": policy.source_doc,
                    }
                return None
        except Exception as e:
            logger.error("Policy lookup failed", name=name, error=str(e))
            return None

    def get_policy(self, name: str):
        return _run_async(self._get_policy_async(name))

    async def _list_policies_async(self):
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Policy).order_by(Policy.name.asc()))
                rows = result.scalars().all()
                return [
                    {
                        "id": r.id,
                        "name": r.name,
                        "description": r.description,
                        "required_role": r.required_role,
                        "is_active": r.is_active,
                        "version": r.policy_version,
                        "source_doc": r.source_doc,
                        "created_by": r.created_by,
                        "modified_by": r.modified_by,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error("Policy listing failed", error=str(e))
            return []

    def list_policies(self):
        return _run_async(self._list_policies_async())


# ─── Singleton ────────────────────────────────────────────────────────────────
audit_logger = AuditLogger()
