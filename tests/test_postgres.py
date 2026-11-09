import json
import os
import uuid
from decimal import Decimal

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url

from alembic import command
from sentinel.db import SessionLocal, get_engine, init_db
from sentinel.investigation import get_run, investigate
from sentinel.models import Candle, Coverage, Evidence, IngestionRun, InvestigationRun, Swap
from sentinel.pipeline import ROOT, import_snapshot, restore, scenario, seed
from sentinel.service import Context, evidence, window_metrics

pytestmark = pytest.mark.postgres


@pytest.fixture
def pg_schema(monkeypatch):
    """Own a random schema; never truncate or drop pre-existing application data."""
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL required: real PostgreSQL integration NOT RUN")
    assert url.startswith(("postgresql://", "postgresql+psycopg://"))
    schema = "sentinel_test_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setenv("DATABASE_URL", scoped.render_as_string(hide_password=False))
    try:
        yield schema
    finally:
        get_engine().dispose()
        assert schema.startswith("sentinel_test_") and len(schema) == 46
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def context(item):
    return Context(**{k: item[k] for k in ("source", "snapshot_id", "start", "end")})


def test_postgresql_real_roundtrip_idempotency_and_recovery(pg_schema):
    init_db()
    assert get_engine().dialect.name == "postgresql"
    original = seed()["snapshots"][0]
    c = context(original)
    first = window_metrics(c)
    assert seed()["snapshots"][0]["snapshot_id"] == c.snapshot_id
    assert window_metrics(c) == first
    assert first["row_count"] == 60
    with SessionLocal() as session:
        row = session.scalars(select(Candle).where(Candle.snapshot_id == c.snapshot_id)).first()
        assert isinstance(row.base_volume, Decimal)
    fault = scenario("missing")["snapshots"][0]
    assert restore(fault["snapshot_id"])["snapshot_id"] == c.snapshot_id
    assert window_metrics(c) == first


def test_postgresql_actual_alembic_migration_and_exact_storage(pg_schema):
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(config, "head")
    engine = get_engine()
    with engine.connect() as connection:
        assert connection.scalar(text("select current_schema()")) == pg_schema
        assert connection.scalar(text("select version_num from alembic_version")) == "0002"
    tables = inspect(engine).get_table_names(schema=pg_schema)
    assert {
        "snapshots",
        "raw_batches",
        "cex_candles",
        "dex_swaps",
        "coverage",
        "evidence",
        "investigation_runs",
    } <= set(tables)
    original = seed()["snapshots"][0]
    with SessionLocal() as session:
        row = session.scalars(
            select(Candle)
            .where(Candle.snapshot_id == original["snapshot_id"])
            .order_by(Candle.open_time)
        ).first()
        assert row.base_volume == Decimal("171.72810000")
        columns = inspect(engine).get_columns("cex_candles", schema=pg_schema)
        storage = next(c["type"] for c in columns if c["name"] == "base_volume")
        assert storage.precision == 78 and storage.scale == 30


def test_postgresql_interruption_rolls_back_checkpoint_then_precise_resume(pg_schema):
    init_db()
    manifest = json.loads((ROOT / "fixtures/cex_manifest.json").read_text())
    import csv

    rows = list(csv.reader((ROOT / "fixtures/cex.csv").read_text().splitlines()))
    rows[0][5] = "123.123456789012345678901234567890"
    with pytest.raises(RuntimeError, match="interruption"):
        import_snapshot("cex", rows, manifest, interrupt_after=3)
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Candle)) == 0
        failed = session.scalars(select(IngestionRun)).one()
        assert failed.status == "failed" and failed.checkpoint["processed"] == 0
    item = import_snapshot("cex", rows, manifest)
    with SessionLocal() as session:
        first = session.scalars(
            select(Candle)
            .where(Candle.snapshot_id == item["snapshot_id"])
            .order_by(Candle.open_time)
        ).first()
        assert first.base_volume == Decimal(rows[0][5])
        successful = session.scalars(
            select(IngestionRun).where(IngestionRun.status == "success")
        ).one()
        assert successful.checkpoint == {"processed": 60, "total": 60}
    assert window_metrics(context(item))["coverage"]["complete"]
    before = window_metrics(context(item))
    import_snapshot("cex", rows, manifest)
    assert window_metrics(context(item)) == before


def test_postgresql_zero_swaps_coverage_and_investigation_evidence_persist(pg_schema):
    init_db()
    manifest = json.loads((ROOT / "fixtures/dex_manifest.json").read_text())
    item = import_snapshot("dex", [], manifest)
    c = context(item)
    metrics = window_metrics(c)
    assert metrics["row_count"] == 0 and metrics["coverage"]["complete"]
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Swap)) == 0
        assert session.scalar(select(func.count()).select_from(Coverage)) == 20
    result = investigate(c, "Check data completeness for this window.", baseline="A")
    assert result["report"]["diagnosis"] == "no_issue_found_in_checks"
    assert get_run(result["run_id"]) == result
    refs = result["report"]["evidence_refs"]
    registered = evidence(refs, c.snapshot_id)
    assert registered and all(e["snapshot_id"] == c.snapshot_id for e in registered)
    with SessionLocal() as session:
        persisted = session.get(InvestigationRun, result["run_id"])
        assert persisted.payload["report"]["window"] == result["report"]["window"]
        assert all(session.get(Evidence, eid) is not None for eid in refs)
