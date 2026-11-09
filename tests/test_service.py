from datetime import timedelta

import pytest
from pydantic import ValidationError

from sentinel.db import init_db
from sentinel.pipeline import reset, scenario, seed
from sentinel.service import Context, evidence, ingestion_status, quality_findings, window_metrics


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'service.db'}")
    init_db()


def context(item):
    return Context(**{k: item[k] for k in ("source", "snapshot_id", "start", "end")})


def test_incomplete_and_unequal_minute_windows_do_not_claim_comparable_change():
    normal = context(seed()["snapshots"][0])
    missing = context(scenario("missing")["snapshots"][0])
    for scope in (missing, normal.model_copy(update={"end": normal.start + timedelta(minutes=3)})):
        comparison = window_metrics(scope)["comparison"]
        assert comparison["status"] == "insufficient_samples"
        assert comparison["change_pct"] is None


def test_half_open_window_and_boundaries():
    c = context(seed()["snapshots"][0])
    first = c.model_copy(update={"end": c.start + timedelta(minutes=1)})
    assert window_metrics(first)["row_count"] == 1
    outside = c.model_copy(update={"start": c.start - timedelta(minutes=1)})
    assert not window_metrics(outside)["coverage"]["window_covered"]
    assert any(
        f["rule"] == "window_outside_snapshot" for f in quality_findings(outside)["findings"]
    )
    with pytest.raises(ValidationError):
        Context(
            source="cex",
            snapshot_id=c.snapshot_id,
            start="2025-01-01T00:00:00",
            end="2025-01-01T01:00:00Z",
        )
    with pytest.raises(ValidationError):
        Context(
            source="cex", snapshot_id=c.snapshot_id, start=c.start, end=c.start + timedelta(days=8)
        )


def test_evidence_content_scope_and_sql_injection():
    original = seed()["snapshots"][0]
    c = context(original)
    metrics = window_metrics(c)
    e = evidence(metrics["evidence_ids"], c.snapshot_id)[0]
    assert e["base_volume"] == metrics["base_volume"]
    assert e["start"] == metrics["start"]
    assert e["snapshot_id"] == c.snapshot_id
    fault = context(scenario("missing")["snapshots"][0])
    with pytest.raises(ValueError, match="bound snapshot"):
        evidence(metrics["evidence_ids"], fault.snapshot_id)
    with pytest.raises(ValueError):
        window_metrics(c.model_copy(update={"snapshot_id": "' OR 1=1 --"}))
    with pytest.raises(ValueError):
        evidence(["../../.env"], c.snapshot_id)
    assert ingestion_status(c)["coverage"]["complete"]


def test_reset_only_fault_namespace():
    c = context(seed()["snapshots"][0])
    with pytest.raises(ValueError, match="isolated fault"):
        reset(c.snapshot_id)
    fault = scenario("missing")["snapshots"][0]
    reset(fault["snapshot_id"])
    assert window_metrics(c)["row_count"] == 60
