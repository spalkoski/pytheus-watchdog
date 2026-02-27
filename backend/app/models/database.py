from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from datetime import datetime
from backend.app.core.config import settings

Base = declarative_base()


class Target(Base):
    """Monitored targets (HTTP endpoints, etc.)"""
    __tablename__ = "targets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(String)  # http, tcp, etc.
    url = Column(String)
    interval = Column(Integer)  # seconds
    severity = Column(String)  # critical, warning, info
    config = Column(JSON)  # timeout, expected_status, content_match, etc.
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CheckResult(Base):
    """Individual check results"""
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, index=True)
    target_name = Column(String, index=True)
    status = Column(String)  # up, down, degraded
    response_time = Column(Float, nullable=True)  # milliseconds
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)  # AI triage reasoning for status pages
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)


class Incident(Base):
    """Incidents (grouped failures)"""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    target_name = Column(String, index=True)
    severity = Column(String)
    status = Column(String)  # open, acknowledged, resolved
    title = Column(String)
    description = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
    notification_sent = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)


class DeadManSwitch(Base):
    """Dead man's switch configurations"""
    __tablename__ = "deadman_switches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    token = Column(String, unique=True, index=True)  # unique webhook token
    expected_interval = Column(Integer)  # seconds
    severity = Column(String)
    last_ping = Column(DateTime, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeadManPing(Base):
    """Dead man's switch ping history"""
    __tablename__ = "deadman_pings"

    id = Column(Integer, primary_key=True, index=True)
    switch_id = Column(Integer, index=True)
    switch_name = Column(String, index=True)
    pinged_at = Column(DateTime, default=datetime.utcnow, index=True)
    payload = Column(JSON, nullable=True)  # optional payload from ping


class PlatformStatus(Base):
    """Platform status check results"""
    __tablename__ = "platform_status"

    id = Column(Integer, primary_key=True, index=True)
    platform_name = Column(String, index=True)
    status = Column(String)  # operational, degraded, major_outage, maintenance
    description = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)


# Database engine and session
# Ensure we use the async driver for SQLite
db_url = settings.database_url
if db_url.startswith("sqlite:///"):
    db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

engine = create_async_engine(
    db_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
