"""Case-scoped, source-preserving relational graph storage."""
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, JSON, Integer, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = 'cases'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))


class Entity(Base):
    __tablename__ = 'entities'
    case_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    attrs: Mapped[dict] = mapped_column(JSON, default=dict)


class Source(Base):
    __tablename__ = 'sources'
    case_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Edge(Base):
    __tablename__ = 'edges'
    case_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(80))
    relation: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(80))
    excerpt: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[str] = mapped_column(String(40))
    recorded_at: Mapped[str] = mapped_column(String(40), default=now)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    polarity: Mapped[str] = mapped_column(String(20), default='asserted')
    revision: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (Index('edge_window', 'case_id', 'status', 'occurred_at'),
                      Index('edge_src', 'case_id', 'source'), Index('edge_dst', 'case_id', 'target'))


class Review(Base):
    __tablename__ = 'reviews'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(80), index=True)
    edge_id: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(80), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    digest: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    __table_args__ = (UniqueConstraint('case_id', 'digest'),)


def database(url=None):
    url = url or os.getenv('DATABASE_URL', 'sqlite:///./workbench.db')

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url, pool_pre_ping=True,
                           connect_args={'check_same_thread': False, 'timeout': 30} if url.startswith('sqlite') else {})
    return engine, sessionmaker(engine, expire_on_commit=False)


class IdentityState(Base):
    __tablename__ = 'identity_state'
    case_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)


class IdentityDecision(Base):
    __tablename__ = 'identity_decisions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(80), index=True)
    source: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(80))
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(100))
    before: Mapped[dict] = mapped_column(JSON)
    features: Mapped[dict] = mapped_column(JSON)
    active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Hypothesis(Base):
    __tablename__ = 'hypotheses'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), index=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='unreviewed')
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class AnalysisJob(Base):
    __tablename__ = 'analysis_jobs'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    operation: Mapped[str] = mapped_column(String(30))
    scope: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
