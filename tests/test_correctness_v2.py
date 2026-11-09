"""User-reported correctness regressions, written before the v2 fixes.

Storage/query regressions run against SQLite and independently isolated PostgreSQL.
Fake model results below test accounting only; they are not model evaluations.
"""

import copy
import csv
import json
import os
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.engine import make_url

from sentinel import db, evaluation, investigation, pipeline, service
from sentinel.models import Coverage


@pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.postgres)])
def backend(request, tmp_path, monkeypatch):
    admin = None
    if request.param == "sqlite":
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'regression.db'}")
    else:
        url = os.getenv("TEST_POSTGRES_URL")
        if not url:
            pytest.skip("TEST_POSTGRES_URL required; real PostgreSQL NOT RUN")
        schema = "sentinel_regression_" + uuid.uuid4().hex
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
        monkeypatch.setenv("DATABASE_URL", scoped.render_as_string(hide_password=False))
    db.init_db()
    try:
        yield request.param
    finally:
        db.get_engine().dispose()
        if admin:
            assert schema.startswith("sentinel_regression_") and len(schema) == 52
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


def inputs(source):
    manifest = json.loads((pipeline.ROOT / f"fixtures/{source}_manifest.json").read_text())
    raw = (pipeline.ROOT / manifest["raw_file"]).read_text()
    return (list(csv.reader(raw.splitlines())) if source == "cex" else json.loads(raw)), manifest


def scope(item, **bounds):
    return service.Context(
        **({k: item[k] for k in ("source", "snapshot_id", "start", "end")} | bounds)
    )


@pytest.mark.parametrize("baseline", ["B", "C"])
def test_fallback_report_success_is_not_live_model_success(baseline):
    def row(actual, status, correct, **extra):
        return {
            "category": "fault",
            "result": {
                "model_mode": "live_llm",
                "actual_model_mode": actual,
                "execution_status": status,
                "model_calls": 1,
                "failure": None,
                **extra,
            },
            "score": {
                "success": correct,
                **{
                    k: {"numerator": int(correct), "denominator": 1}
                    for k in ("diagnosis", "numeric", "evidence", "unknown_handling")
                },
            },
        }

    rows = [
        row("live_llm", "completed", True),
        row("live_llm", "completed", False),
        row("deterministic", "fallback", True, failure={"type": "Timeout"}),
        row("test_adapter", "completed", True, model_mode="test_adapter"),
        row("live_llm", "failed", False, failure={"type": "InvalidJSON"}),
    ]
    totals = evaluation.summarize(rows, baseline=baseline)["all"]
    assert totals["system_report_accuracy"] == {"numerator": 3, "denominator": 5}
    assert totals["model_completion_rate"] == {"numerator": 2, "denominator": 5}
    assert totals["model_accuracy"] == {"numerator": 1, "denominator": 5}
    assert totals["completed_model_accuracy"] == {"numerator": 1, "denominator": 2}


@pytest.mark.parametrize("baseline", ["B", "C"])
def test_runner_keeps_successful_fallbacks_in_model_failure_denominator(
    tmp_path, monkeypatch, baseline
):
    from sentinel.llm import ModelSettings

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounting.db'}")
    # Contract test: simulated transport failure, never a live-model evaluation.
    monkeypatch.setattr(ModelSettings, "from_env", lambda: object())
    real = investigation.investigate

    def failed_transport(ctx, question, **kwargs):
        result = real(ctx, question, mode="deterministic", baseline="A", persist=False)
        return {
            **result,
            "model_mode": "live_llm",
            "actual_model_mode": "deterministic",
            "execution_status": "fallback",
            "failure": {"type": "SimulatedTimeout"},
        }

    monkeypatch.setattr(investigation, "investigate", failed_transport)
    artifact = evaluation.run_evaluation("development", baseline, True, tmp_path / "contract.json")
    totals = artifact["summary"]["all"]
    assert totals["system_report_accuracy"] == {"numerator": 8, "denominator": 8}
    assert totals["model_completion_rate"] == {"numerator": 0, "denominator": 8}
    assert totals["model_accuracy"] == {"numerator": 0, "denominator": 8}
    assert len(artifact["model_failures"]) == 8 and not artifact["failures"]


def test_conflicts_include_source_fields_not_present_in_normalized_schema(backend):
    rows, manifest = inputs("cex")
    conflicting = copy.deepcopy(rows[-1])
    conflicting[9] = "123.456"  # taker-buy field was formerly ignored by duplicate comparison
    ctx = scope(pipeline.import_snapshot("cex", rows + [conflicting], manifest))
    assert service.ingestion_status(ctx)["record_conflicts"] == 1
    assert service.window_metrics(ctx)["coverage"]["complete"]
    assert service.quality_findings(ctx)["has_data_issue"]
    short = ctx.model_copy(update={"end": ctx.start + timedelta(minutes=2)})
    assert service.ingestion_status(short)["record_conflicts"] == 0
    assert not service.quality_findings(short)["has_data_issue"]


@pytest.mark.parametrize("source", ["cex", "dex"])
@pytest.mark.parametrize("invalid_first", [False, True])
def test_conflicting_key_is_retained_even_when_one_value_cannot_be_parsed(
    backend, source, invalid_first
):
    rows, manifest = inputs(source)
    bad = copy.deepcopy(rows[0])
    bad[5 if source == "cex" else "amount0"] = "invalid-value"
    payload = [bad, rows[0]] if invalid_first else [rows[0], bad]
    ctx = scope(pipeline.import_snapshot(source, payload, manifest))
    assert service.ingestion_status(ctx)["record_conflicts"] == 1
    assert service.ingestion_status(ctx)["quarantined_rows"] == 1
    assert service.window_metrics(ctx)["row_count"] == 1
    pipeline.import_snapshot(source, payload, manifest)
    assert service.ingestion_status(ctx)["record_conflicts"] == 1


def test_quarantine_half_open_scope_and_known_issue_precedes_uncertainty(backend):
    rows, manifest = inputs("cex")
    extra = [copy.deepcopy(rows[i]) for i in (1, 3, 0)]
    extra[0][5] = extra[1][5] = "bad-volume"
    extra[2][0] = "bad-time"
    full = scope(pipeline.import_snapshot("cex", rows + extra, manifest))
    ctx = full.model_copy(
        update={
            "start": full.start + timedelta(minutes=1),
            "end": full.start + timedelta(minutes=3),
        }
    )
    # The bad row exactly at end is outside; the bad row exactly at start is inside.
    status = service.ingestion_status(ctx)
    assert status["quarantine_scope"] == {"in_window": 1, "outside_window": 1, "unknown_time": 1}
    assert status["quarantined_rows_total"] == 3
    report = investigation.investigate(ctx, "Check completeness", persist=False)
    assert report["report"]["diagnosis"] == "observed_data_issue"


def test_null_dex_hash_is_quarantined_using_registered_block_time(backend):
    rows, manifest = inputs("dex")
    bad = {**rows[0], "block_hash": None}
    ctx = scope(pipeline.import_snapshot("dex", rows + [bad], manifest))
    status = service.ingestion_status(ctx)
    assert status["quarantine_scope"] == {"in_window": 1, "outside_window": 0, "unknown_time": 0}
    assert service.quality_findings(ctx)["has_data_issue"]


def test_dex_no_block_anchor_cannot_certify_an_empty_window(backend):
    _, manifest = inputs("dex")
    manifest["blocks"] = []
    ctx = scope(pipeline.import_snapshot("dex", [], manifest))
    coverage = service.window_metrics(ctx)["coverage"]
    assert coverage["window_covered"] and not coverage["complete"]
    assert not coverage["coverage_known"]
    assert service.ingestion_status(ctx)["lag_seconds"] is None
    assert (
        investigation.investigate(ctx, "Check completeness", persist=False)["report"]["diagnosis"]
        == "insufficient_evidence"
    )


@pytest.mark.parametrize("source", ["cex", "dex"])
def test_identical_duplicates_and_conflicting_values_are_distinct(backend, source):
    rows, manifest = inputs(source)
    first = rows[0]
    conflict = copy.deepcopy(first)
    conflict[5 if source == "cex" else "amount0"] = "999.123" if source == "cex" else "999123000"
    payload = [first, copy.deepcopy(first), conflict]
    item = pipeline.import_snapshot(source, payload, manifest)
    ctx = scope(item)
    status = service.ingestion_status(ctx)
    assert status["identical_duplicates"] == 1
    assert status["record_conflicts"] == 1
    assert service.window_metrics(ctx)["row_count"] == 1
    quality = service.quality_findings(ctx)
    finding = next(f for f in quality["findings"] if f["rule"] == "conflicting_records")
    assert finding["severity"] == "error"
    record = finding["actual"]["records"][0]
    assert record["row_index"] == 2 and record["raw_batch_id"] == "raw-" + ctx.snapshot_id
    assert record["accepted"] != record["incoming"]
    assert (
        service.evidence(finding["evidence_ids"], ctx.snapshot_id)[0]["actual"] == finding["actual"]
    )
    pipeline.import_snapshot(source, payload, manifest)
    assert service.ingestion_status(ctx)["record_conflicts"] == 1
    assert service.ingestion_status(ctx)["identical_duplicates"] == 1


@pytest.mark.parametrize("source", ["cex", "dex"])
def test_outside_bad_rows_do_not_contaminate_query_window(backend, source):
    rows, manifest = inputs(source)
    bad = copy.deepcopy(rows[-1])
    bad[5 if source == "cex" else "amount0"] = "not-a-number"
    item = pipeline.import_snapshot(source, rows + [bad], manifest)
    ctx = scope(item)
    short = ctx.model_copy(
        update={"end": ctx.start + timedelta(minutes=2 if source == "cex" else 1)}
    )
    status = service.ingestion_status(short)
    assert status["quarantined_rows"] == 0
    assert status["quarantine_scope"] == {"in_window": 0, "outside_window": 1, "unknown_time": 0}
    assert not service.quality_findings(short)["has_data_issue"]
    assert (
        investigation.investigate(short, "Check completeness", persist=False)["report"]["diagnosis"]
        == "no_issue_found_in_checks"
    )
    assert service.ingestion_status(ctx)["quarantine_scope"]["in_window"] == 1


@pytest.mark.parametrize("source", ["cex", "dex"])
def test_unknown_time_bad_rows_require_uncertainty_not_local_issue(backend, source):
    rows, manifest = inputs(source)
    bad = copy.deepcopy(rows[0])
    if source == "cex":
        bad[0] = "unknown-time"
    else:
        bad.update(block_number="unknown-block", event_time="unknown-time")
    ctx = scope(pipeline.import_snapshot(source, rows + [bad], manifest))
    status = service.ingestion_status(ctx)
    assert status["quarantined_rows"] == 0
    assert status["quarantine_scope"] == {"in_window": 0, "outside_window": 0, "unknown_time": 1}
    findings = service.quality_findings(ctx)
    assert not findings["has_data_issue"] and findings["has_unresolved_evidence"]
    assert any(f["rule"] == "unlocated_invalid_rows" for f in findings["findings"])
    report = investigation.investigate(ctx, "Check completeness", persist=False)["report"]
    assert report["diagnosis"] == "insufficient_evidence"
    assert all("did not find a data issue" not in f["statement"] for f in report["facts"])


def test_existing_evaluation_artifact_is_rejected_before_any_case_runs(tmp_path, monkeypatch):
    target = tmp_path / "prior.json"
    target.write_bytes(b"prior-evaluation-bytes")
    monkeypatch.setattr(
        evaluation,
        "prepare_case",
        lambda _: pytest.fail("old output must be rejected before evaluation"),
    )
    with pytest.raises(ValueError, match="already exists"):
        evaluation.run_evaluation(output=target)
    assert target.read_bytes() == b"prior-evaluation-bytes"


@pytest.mark.parametrize("position", ["between", "trailing", "irregular"])
def test_dex_empty_time_window_uses_overlapping_predecessor_block(backend, position):
    _, manifest = inputs("dex")
    if position == "irregular":
        for b in manifest["blocks"][2:]:
            b["timestamp"] = (pipeline.utc(b["timestamp"]) + timedelta(seconds=36)).isoformat()
        manifest["end"] = manifest["expected_end"] = (
            pipeline.utc(manifest["end"]) + timedelta(seconds=36)
        ).isoformat()
    item = pipeline.import_snapshot("dex", [], manifest)
    base = scope(item)
    if position == "trailing":
        start = pipeline.utc(manifest["blocks"][-1]["timestamp"]) + timedelta(seconds=1)
        end = base.end - timedelta(seconds=1)
        predecessor = manifest["blocks"][-1]["number"]
    else:
        start = base.start + timedelta(seconds=15)
        end = base.start + timedelta(seconds=40 if position == "irregular" else 20)
        predecessor = manifest["blocks"][1]["number"]
    ctx = base.model_copy(update={"start": start, "end": end})
    metrics = service.window_metrics(ctx)
    assert metrics["row_count"] == 0
    assert metrics["coverage"]["expected"] == 1
    assert metrics["coverage"]["complete"]
    assert service.ingestion_status(ctx)["lag_seconds"] == 0
    assert not service.quality_findings(ctx)["has_data_issue"]
    with db.SessionLocal() as session:
        session.execute(
            delete(Coverage).where(
                Coverage.snapshot_id == ctx.snapshot_id, Coverage.block_number == predecessor
            )
        )
        session.commit()
    coverage = service.window_metrics(ctx)["coverage"]
    assert not coverage["complete"] and coverage["missing"] == 1
    assert service.ingestion_status(ctx)["lag_seconds"] == int((end - start).total_seconds())
    assert service.quality_findings(ctx)["has_data_issue"]
