import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from sentinel.db import SessionLocal, init_db
from sentinel.models import Coverage, IngestionRun, Quarantine, Swap
from sentinel.pipeline import ROOT, import_snapshot, parse_candle, restore, scenario, seed
from sentinel.service import Context, ingestion_status, quality_findings, window_metrics


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    init_db()


def ctx(item):
    return Context(**{k: item[k] for k in ("source", "snapshot_id", "start", "end")})


def test_timestamp_contract_and_precision():
    manifest = json.loads((ROOT / "fixtures/cex_manifest.json").read_text())
    import csv

    row = next(csv.reader((ROOT / "fixtures/cex.csv").read_text().splitlines()))
    parsed = parse_candle(row, manifest)
    assert parsed["open_time"] == datetime(2025, 1, 1, tzinfo=timezone.utc)
    row[5] = "0.123456789012345678901234567890"
    assert parse_candle(row, manifest)["base_volume"] == Decimal(row[5])
    too_precise = list(row)
    too_precise[5] = "0.1234567890123456789012345678901"
    with pytest.raises(ValueError, match="precision"):
        parse_candle(too_precise, manifest)
    wrong = {**manifest, "timestamp_unit": "ms"}
    with pytest.raises(ValueError, match="date contract"):
        parse_candle(row, wrong)
    old = {
        **manifest,
        "start": "2024-12-31T00:00:00+00:00",
        "end": "2025-01-01T00:00:00+00:00",
        "timestamp_unit": "ms",
    }
    row[0] = str(int(datetime(2024, 12, 31, tzinfo=timezone.utc).timestamp()) * 1000)
    row[6] = str(int(row[0]) + 59999)
    assert parse_candle(row, old)["open_time"].year == 2024


def test_idempotency_missing_restore_and_isolation():
    originals = seed()["snapshots"]
    before = [window_metrics(ctx(x)) for x in originals]
    assert before[0]["row_count"] == 60
    assert before[0]["base_volume"] == "8894.44440000"
    assert before[0]["number_of_trades"] == 54290
    assert before[1]["row_count"] == 7
    assert before[1]["token0_volume"] == "70"
    assert seed()["snapshots"] == originals
    assert [window_metrics(ctx(x)) for x in originals] == before
    faulty = scenario("missing")["snapshots"]
    assert window_metrics(ctx(faulty[0]))["coverage"]["missing"] == 3
    assert window_metrics(ctx(faulty[1]))["coverage"]["missing"] == 3
    assert quality_findings(ctx(faulty[0]))["has_data_issue"]
    assert restore(faulty[0]["snapshot_id"])["snapshot_id"] == originals[0]["snapshot_id"]
    assert window_metrics(ctx(originals[0])) == before[0]
    assert window_metrics(ctx(faulty[0]))["coverage"]["missing"] == 3


def test_zero_swaps_are_not_unscanned_blocks():
    manifest = json.loads((ROOT / "fixtures/dex_manifest.json").read_text())
    empty = import_snapshot("dex", [], manifest)
    result = window_metrics(ctx(empty))
    assert result["row_count"] == 0
    assert result["coverage"]["complete"]
    assert result["comparison"]["status"] == "zero_baseline"
    assert not quality_findings(ctx(empty))["has_data_issue"]
    missing = import_snapshot("dex", [], manifest, fault="missing")
    assert quality_findings(ctx(missing))["has_data_issue"]


def test_transaction_rolls_back_data_and_checkpoint_on_interruption():
    manifest = json.loads((ROOT / "fixtures/dex_manifest.json").read_text())
    rows = json.loads((ROOT / "fixtures/dex.json").read_text())
    with pytest.raises(RuntimeError, match="interruption"):
        import_snapshot("dex", rows, manifest, interrupt_after=2)
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Swap)) == 0
        assert session.scalar(select(func.count()).select_from(Coverage)) == 0
        run = session.scalars(select(IngestionRun)).one()
        assert run.status == "failed"
        assert run.checkpoint["processed"] == 0
    resumed = import_snapshot("dex", rows, manifest)
    assert window_metrics(ctx(resumed))["coverage"]["complete"]
    assert window_metrics(ctx(resumed))["row_count"] == 7


def test_invalid_rows_quarantined_no_silent_discard():
    result = scenario("invalid")["snapshots"]
    for item in result:
        c = ctx(item)
        assert quality_findings(c)["has_data_issue"]
        assert ingestion_status(c)["quarantined_rows"] == 1
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Quarantine)) == 2


def test_replay_freshness_and_stale_snapshot_clock():
    for item in seed()["snapshots"]:
        assert ingestion_status(ctx(item))["lag_seconds"] == 0
    stale = scenario("stale")["snapshots"]
    assert ingestion_status(ctx(stale[0]))["lag_seconds"] == 300
    assert ingestion_status(ctx(stale[1]))["lag_seconds"] == 60


def test_order_duplicate_and_hash_mismatch():
    normal = seed()["snapshots"]
    for mode in ("duplicate", "out_of_order"):
        versions = scenario(mode)["snapshots"]
        for a, b in zip(normal, versions, strict=True):
            assert window_metrics(ctx(a))["row_count"] == window_metrics(ctx(b))["row_count"]
            assert not quality_findings(ctx(b))["has_data_issue"]
    manifest = json.loads((ROOT / "fixtures/dex_manifest.json").read_text())
    rows = json.loads((ROOT / "fixtures/dex.json").read_text())
    rows[0]["block_hash"] = "0x" + "0" * 64
    bad = import_snapshot("dex", rows, manifest)
    assert ingestion_status(ctx(bad))["quarantined_rows"] == 1
    assert quality_findings(ctx(bad))["has_data_issue"]


def test_int256_signed_boundaries_preserve_raw_and_reject_overflow():
    manifest = json.loads((ROOT / "fixtures/dex_manifest.json").read_text())
    template = json.loads((ROOT / "fixtures/dex.json").read_text())[0]
    minimum = -(2**255)
    maximum = 2**255 - 1
    row = {**template, "amount0": str(minimum), "amount1": str(maximum)}
    item = import_snapshot("dex", [row], manifest)
    with SessionLocal() as session:
        stored = session.scalars(select(Swap).where(Swap.snapshot_id == item["snapshot_id"])).one()
        assert stored.amount0 == str(minimum)
        assert stored.amount1 == str(maximum)
    assert ingestion_status(ctx(item))["quarantined_rows"] == 0
    for amount0, amount1 in ((minimum - 1, 1), (-1, maximum + 1)):
        invalid = import_snapshot(
            "dex", [{**template, "amount0": str(amount0), "amount1": str(amount1)}], manifest
        )
        assert ingestion_status(ctx(invalid))["quarantined_rows"] == 1
        with SessionLocal() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(Swap)
                    .where(Swap.snapshot_id == invalid["snapshot_id"])
                )
                == 0
            )
