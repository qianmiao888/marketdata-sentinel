from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from sentinel import db, pipeline, service
from sentinel.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "api.db").as_posix())
    db.init_db()
    pipeline.seed()
    with TestClient(app) as test_client:
        yield test_client


def scope(client):
    item = next(s for s in client.get("/snapshots").json() if s["source"] == "cex")
    return {key: item[key] for key in ("source", "snapshot_id", "start", "end")}


def test_http_metrics_quality_and_report_evidence(client):
    context = scope(client)
    metrics = client.get("/metrics", params=context)
    assert metrics.status_code == 200
    assert metrics.json()["row_count"] == 60
    report = client.post(
        "/investigations", json={"context": context, "question": "Check coverage and volume."}
    )
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["report"]["diagnosis"] == "no_issue_found_in_checks"
    assert client.get("/investigations/" + data["run_id"]).json() == data
    for evidence_id in data["report"]["evidence_refs"]:
        response = client.get(
            "/evidence", params={"snapshot_id": context["snapshot_id"], "ids": evidence_id}
        )
        assert response.status_code == 200
        assert response.json()[0]["snapshot_id"] == context["snapshot_id"]


@pytest.mark.parametrize(
    "mutation",
    [
        {"source": "cex; DROP TABLE snapshots"},
        {"snapshot_id": "' OR 1=1 --"},
        {"start": "2025-01-01T00:00:00"},
        {"end": "2025-03-01T00:00:00Z"},
        {"end": "2025-01-01T00:00:00Z"},
    ],
)
def test_invalid_scope_and_sql_like_inputs_rejected(client, mutation):
    params = scope(client) | mutation
    assert client.get("/metrics", params=params).status_code == 422
    assert client.get("/snapshots").status_code == 200


def test_evidence_cross_snapshot_and_path_denied(client):
    context = scope(client)
    eid = client.get("/metrics", params=context).json()["evidence_ids"][0]
    other = next(s for s in service.list_snapshots() if s["source"] == "dex")
    assert (
        client.get(
            "/evidence", params={"snapshot_id": other["snapshot_id"], "ids": eid}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/evidence", params={"snapshot_id": context["snapshot_id"], "ids": "../../.env"}
        ).status_code
        == 422
    )
    assert client.get("/runs", params={"limit": 201}).status_code == 422
    assert (
        client.post(
            "/investigations",
            json={"context": context, "question": "Check volume", "mode": "test_adapter"},
        ).status_code
        == 422
    )
    assert client.get("/investigations/does-not-exist").status_code == 404


def test_outside_snapshot_does_not_claim_full_coverage(client):
    context = scope(client)
    context["start"] = (
        datetime(2025, 1, 1, tzinfo=timezone.utc) - timedelta(minutes=1)
    ).isoformat()
    data = client.get("/quality", params=context).json()
    assert any(f["rule"] == "window_outside_snapshot" for f in data["findings"])


def test_missing_ready_migration_returns_503(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
