from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from sentinel.db import Base


def now():
    return datetime.now(timezone.utc)


class ExactDecimal(TypeDecorator):
    impl = Numeric
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(Text() if dialect.name == "sqlite" else Numeric(78, 30))

    def process_bind_param(self, value, dialect):
        return str(value) if dialect.name == "sqlite" and value is not None else value

    def process_result_value(self, value, dialect):
        return Decimal(value) if value is not None else None


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source: Mapped[str] = mapped_column(String(20), index=True)
    manifest: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RawBatch(Base):
    __tablename__ = "raw_batches"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"))
    checksum: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict] = mapped_column(JSON)
    payload: Mapped[dict] = mapped_column(JSON)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Candle(Base):
    __tablename__ = "cex_candles"
    __table_args__ = (UniqueConstraint("snapshot_id", "source", "symbol", "interval", "open_time"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), index=True)
    source: Mapped[str] = mapped_column(String(30), default="binance")
    symbol: Mapped[str] = mapped_column(String(20), default="ETHUSDT")
    interval: Mapped[str] = mapped_column(String(5), default="1m")
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[Decimal] = mapped_column(ExactDecimal())
    high: Mapped[Decimal] = mapped_column(ExactDecimal())
    low: Mapped[Decimal] = mapped_column(ExactDecimal())
    close: Mapped[Decimal] = mapped_column(ExactDecimal())
    base_volume: Mapped[Decimal] = mapped_column(ExactDecimal())
    quote_volume: Mapped[Decimal] = mapped_column(ExactDecimal())
    number_of_trades: Mapped[int | None] = mapped_column(Integer)
    raw_batch_id: Mapped[str] = mapped_column(ForeignKey("raw_batches.id"))


class Swap(Base):
    __tablename__ = "dex_swaps"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "chain_id", "pool", "block_hash", "tx_hash", "log_index"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), index=True)
    chain_id: Mapped[int] = mapped_column(Integer)
    pool: Mapped[str] = mapped_column(String(42))
    block_number: Mapped[int] = mapped_column(Integer)
    block_hash: Mapped[str] = mapped_column(String(66))
    tx_hash: Mapped[str] = mapped_column(String(66))
    log_index: Mapped[int] = mapped_column(Integer)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    amount0: Mapped[str] = mapped_column(Text)
    amount1: Mapped[str] = mapped_column(Text)
    token_metadata: Mapped[dict] = mapped_column(JSON)
    raw_batch_id: Mapped[str] = mapped_column(ForeignKey("raw_batches.id"))


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("snapshots.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30))
    checkpoint: Mapped[dict] = mapped_column(JSON)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Coverage(Base):
    __tablename__ = "coverage"
    __table_args__ = (UniqueConstraint("snapshot_id", "block_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), index=True)
    block_number: Mapped[int] = mapped_column(Integer)
    block_hash: Mapped[str] = mapped_column(String(66))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Quarantine(Base):
    __tablename__ = "quarantine"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), index=True)
    raw_batch_id: Mapped[str] = mapped_column(ForeignKey("raw_batches.id"))
    row_index: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSON)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)


class QualityFinding(Base):
    __tablename__ = "quality_findings"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class InvestigationRun(Base):
    __tablename__ = "investigation_runs"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshots.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
