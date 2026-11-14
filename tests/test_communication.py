"""Correctness of frozen bilingual facts, recovery receipts and scope isolation."""

import copy
import json
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text
from sqlalchemy.engine import make_url

from sentinel import communication as comm
from sentinel import db, investigation, pipeline, service
from sentinel.api import app
from sentinel.models import Evidence, InvestigationRun
from sentinel.workbench_state import current_bundle, scope_key


@pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.postgres)])
def backend(request, tmp_path, monkeypatch):
    admin = None
    if request.param == "sqlite":
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'communication.db'}")
    else:
        url = os.getenv("TEST_POSTGRES_URL")
        if not url:
            pytest.skip("TEST_POSTGRES_URL required; PostgreSQL NOT RUN")
        schema = "sentinel_communication_" + uuid4().hex
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
        monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    db.init_db()
    try:
        yield
    finally:
        db.get_engine().dispose()
        if admin:
            assert schema.startswith("sentinel_communication_") and len(schema) == 55
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


def check(item):
    ctx = service.Context(**{k: item[k] for k in ("source", "snapshot_id", "start", "end")})
    return investigation.investigate(ctx, "Check completeness before citation", baseline="A")


def missing_report():
    return check(pipeline.scenario("missing")["snapshots"][0])


def test_bilingual_bundle_uses_exact_frozen_report_and_real_lineage(backend):
    report = missing_report()
    bundle = comm.build_bundle(report["run_id"])
    assert bundle["report"] == report["report"]
    assert bundle["status"] == "draft_requires_review"
    assert bundle["provenance"]["synthetic"] is False
    assert bundle["provenance"]["transform"] == "missing"
    for metric in bundle["metrics"]:
        assert metric in bundle["report"]["metrics"]
        if metric["name"] not in comm.BUSINESS_METRICS:
            continue
        for language in ("markdown_zh", "markdown_en"):
            assert metric["value"] in bundle[language]
            assert metric["unit"] in bundle[language]
            assert all(eid in bundle[language] for eid in metric["evidence_ids"])
    assert "6933.44030000" in bundle["markdown_zh"]
    assert "not an exchange incident" in bundle["markdown_en"]
    assert "未关联恢复" in bundle["issue_markdown"]


def test_recovery_persists_pair_preserves_old_report_and_repeats_idempotently(backend):
    before = missing_report()
    original = copy.deepcopy(before)
    rec = comm.recover(before["run_id"])
    assert rec["restore_status"] == "completed"
    assert rec["verification_status"] == "no_issue_found_in_checks"
    assert rec["snapshot_id"] != rec["restored_snapshot_id"]
    bundle = comm.build_bundle(before["run_id"], rec["id"])
    versions = bundle["comparison"]["versions"]
    assert len(versions) == 2
    before_metrics, after_metrics = [
        {m["name"]: m["value"] for m in v["report"]["metrics"]} for v in versions
    ]
    assert before_metrics["coverage_missing"] == "3"
    assert after_metrics["coverage_missing"] == "0"
    assert Decimal(after_metrics["base_volume"]) == Decimal("8894.4444")
    assert "not market growth or decline" in bundle["markdown_en"]
    assert investigation.get_run(before["run_id"]) == original
    assert comm.recover(before["run_id"])["restored_snapshot_id"] == rec["restored_snapshot_id"]
    assert comm.build_bundle(rec["after_run_id"], rec["id"])["recovery"] == rec


@pytest.mark.parametrize("source,other_window", [("cex", False), ("dex", False), ("cex", True)])
def test_unrelated_reports_cannot_borrow_recovery(backend, source, other_window):
    before = missing_report()
    rec = comm.recover(before["run_id"])
    item = next(s for s in service.list_snapshots() if s["source"] == source)
    if other_window:
        item["end"] = "2025-01-01T00:30:00+00:00"
    unrelated = check(item)
    with pytest.raises(ValueError, match="not associated"):
        comm.build_bundle(unrelated["run_id"], rec["id"])


def test_tampered_report_or_deleted_evidence_blocks_exports(backend):
    before = missing_report()
    with db.SessionLocal() as session:
        row = session.get(InvestigationRun, before["run_id"])
        changed = copy.deepcopy(row.payload)
        changed["report"]["metrics"][0]["value"] = "999999"
        row.payload = changed
        session.commit()
    with pytest.raises(ValueError, match="numbers differ"):
        comm.build_bundle(before["run_id"])
    before = missing_report()
    with db.SessionLocal() as session:
        session.execute(delete(Evidence).where(Evidence.id == before["report"]["evidence_refs"][0]))
        session.commit()
    with pytest.raises(ValueError, match="not registered"):
        comm.build_bundle(before["run_id"])


def test_changed_registered_evidence_content_is_not_trusted(backend):
    before = missing_report()
    with db.SessionLocal() as session:
        row = session.get(Evidence, before["report"]["evidence_refs"][0])
        changed = copy.deepcopy(row.payload)
        changed["source"] = "dex"
        row.payload = changed
        session.commit()
    with pytest.raises(ValueError, match="checksum mismatch"):
        comm.build_bundle(before["run_id"])


@pytest.mark.parametrize("stage", ["replay", "verification"])
def test_failed_recovery_never_claims_resolution(backend, monkeypatch, stage):
    before = missing_report()

    def fail(*args, **kwargs):
        raise RuntimeError("private local path must not leak")

    monkeypatch.setattr(
        pipeline if stage == "replay" else investigation,
        "restore" if stage == "replay" else "investigate",
        fail,
    )
    rec = comm.recover(before["run_id"])
    assert rec["restore_status"] == ("failed" if stage == "replay" else "completed")
    assert rec["verification_status"] == "failed"
    assert rec["after_run_id"] is None
    bundle = comm.build_bundle(before["run_id"], rec["id"])
    assert bundle["recovery"] == rec
    assert "private local path" not in json.dumps(bundle)


def test_incomplete_recheck_is_unresolved_not_success(backend, monkeypatch):
    before = missing_report()
    monkeypatch.setattr(pipeline, "restore", lambda sid: {"snapshot_id": sid})
    rec = comm.recover(before["run_id"])
    assert rec["restore_status"] == "completed"
    assert rec["verification_status"] == "unresolved"


def test_failed_initial_checks_yield_unknown_not_normal(backend, monkeypatch):
    item = pipeline.seed()["snapshots"][0]

    def fail(ctx):
        raise RuntimeError("data unavailable")

    monkeypatch.setattr(service, "window_metrics", fail)
    result = check(item)
    bundle = comm.build_bundle(result["run_id"])
    assert bundle["report"]["diagnosis"] == "insufficient_evidence"
    assert "不足以判断" in bundle["judgment_zh"]
    assert not any(m["name"] == "base_volume" for m in bundle["metrics"])


def test_empty_cex_is_missing_but_empty_scanned_dex_is_not(backend):
    for source in ("cex", "dex"):
        manifest = json.loads((pipeline.ROOT / f"fixtures/{source}_manifest.json").read_text())
        item = pipeline.import_snapshot(source, [], manifest)
        bundle = comm.build_bundle(check(item)["run_id"])
        assert bundle["report"]["diagnosis"] == (
            "observed_data_issue" if source == "cex" else "no_issue_found_in_checks"
        )
        if source == "dex":
            assert "Synthetic replay" in bundle["markdown_en"]
            assert any(m["unit"] == "USDC (token0, one side)" for m in bundle["metrics"])


def test_http_communication_recovery_and_validation(backend):
    before = missing_report()
    with TestClient(app) as client:
        path = f"/investigations/{before['run_id']}/communication"
        assert client.get(path).status_code == 200
        rec = client.post("/recoveries", json={"before_run_id": before["run_id"]})
        assert rec.status_code == 200
        assert client.get(path, params={"recovery_id": rec.json()["id"]}).status_code == 200
        assert client.get(path, params={"recovery_id": "unknown"}).status_code == 422
        assert (
            client.post(
                "/recoveries", json={"before_run_id": before["run_id"], "path": "../raw"}
            ).status_code
            == 422
        )
        assert client.post("/recoveries", json={"before_run_id": "unknown"}).status_code == 422


@pytest.mark.parametrize("source", ["cex", "dex"])
@pytest.mark.parametrize("export_role", ["without_recovery", "before", "after"])
def test_http_export_keeps_registered_evidence_hashes_and_deliverable_facts(
    backend, source, export_role
):
    item = next(
        item for item in pipeline.scenario("missing")["snapshots"] if item["source"] == source
    )
    before = check(item)
    receipt = comm.recover(before["run_id"]) if export_role != "without_recovery" else None
    run_id = receipt["after_run_id"] if export_role == "after" else before["run_id"]
    with TestClient(app) as client:
        response = client.get(
            f"/investigations/{run_id}/communication",
            params={"recovery_id": receipt["id"]} if receipt else {},
        )
        assert response.status_code == 200, response.text
        exported = response.json()

    groups = [(exported["report"], exported["evidence"])]
    if receipt:
        assert {v["role"] for v in exported["comparison"]["versions"]} == {"before", "after"}
        groups.extend(
            (version["report"], version["evidence"])
            for version in exported["comparison"]["versions"]
        )
    for report, evidence in groups:
        registered = service.evidence(report["evidence_refs"], report["snapshot_id"])
        assert evidence
        for entry in evidence:
            # Use the existing registration algorithm on the actual exported payload.
            # Only transport fields are excluded; evidence_ids is NOT exempted.
            assert entry["id"].startswith("e-")
            payload = {key: value for key, value in entry.items() if key not in {"id", "kind"}}
            expected_id = "e-" + pipeline.digest({"kind": entry["kind"], "payload": payload})[:32]
            assert entry["id"] == expected_id, (report["snapshot_id"], entry["kind"])
        assert evidence == registered
        assert report["source"] == exported["context"]["source"]
        for bound in ("start", "end"):
            assert pipeline.utc(report["window"][bound]) == pipeline.utc(exported["context"][bound])
        for text_key in ("markdown_zh", "markdown_en", "issue_markdown"):
            text = exported[text_key]
            assert report["snapshot_id"] in text
            for metric in report["metrics"]:
                if metric["name"] in comm.BUSINESS_METRICS:
                    assert (
                        f"| {metric['value']} | {metric['unit']} | "
                        f"{', '.join(metric['evidence_ids'])} |"
                    ) in text
    assert exported["metrics"] == exported["report"]["metrics"]
    for text_key in ("markdown_zh", "markdown_en", "issue_markdown"):
        assert (
            f"UTC [{exported['context']['start']}, {exported['context']['end']})"
            in exported[text_key]
        )


def test_changed_or_invalid_query_cannot_reuse_business_bundle():
    params = {
        "source": "cex",
        "snapshot_id": "s-fixed",
        "start": "2025-01-01T00:00:00Z",
        "end": "2025-01-01T01:00:00Z",
    }
    key = scope_key(params, "Question")
    state = {"scope_key": key, "bundle": {"report": "old"}}
    assert current_bundle(state, key) == state["bundle"]
    equivalent = {**params, "start": "2025-01-01T08:00:00+08:00"}
    assert scope_key(equivalent, "Question") == key
    for mutation in (
        {"source": "dex"},
        {"snapshot_id": "s-other"},
        {"end": "2025-01-01T00:30:00Z"},
    ):
        assert current_bundle(state, scope_key(params | mutation, "Question")) is None
    assert current_bundle(state, scope_key(params, "Different question")) is None
    assert current_bundle(state, scope_key(params, "Question", "live_llm", "C")) is None
    with pytest.raises(ValueError):
        scope_key(params | {"end": params["start"]}, "Question")
