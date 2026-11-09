import os

import pytest

from sentinel.collectors import collect_cex, collect_dex
from sentinel.db import init_db
from sentinel.service import Context, window_metrics


@pytest.mark.external
def test_public_binance_archive_checksum_and_schema(tmp_path, monkeypatch):
    if os.getenv("RUN_EXTERNAL_SMOKE") != "1":
        pytest.skip("RUN_EXTERNAL_SMOKE=1 required; network NOT RUN")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'external.db'}")
    init_db()
    item = collect_cex("2025-01-01")
    context = Context(**{k: item[k] for k in ("source", "snapshot_id", "start", "end")})
    metrics = window_metrics(context)
    assert metrics["coverage"]["complete"] and metrics["row_count"] == 1440


@pytest.mark.external
def test_configured_historical_dex_rpc(tmp_path, monkeypatch):
    rpc = os.getenv("ETH_RPC_URL")
    if os.getenv("RUN_EXTERNAL_SMOKE") != "1" or not rpc:
        pytest.skip("RUN_EXTERNAL_SMOKE=1 and ETH_RPC_URL required; real DEX NOT RUN")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'dex-external.db'}")
    init_db()
    item = collect_dex(rpc)
    context = Context(**{k: item[k] for k in ("source", "snapshot_id", "start", "end")})
    assert window_metrics(context)["coverage"]["complete"]
