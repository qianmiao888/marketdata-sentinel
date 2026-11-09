"""Offline trust-boundary, fallback and documented HTTP protocol checks."""

import json
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from sentinel import investigation as inv
from sentinel.llm import ChatAdapter, ModelSettings, ModelUnavailable
from sentinel.service import Context


@pytest.fixture
def ctx():
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return Context(
        source="cex", snapshot_id="f" * 32, start=start, end=start + timedelta(minutes=10)
    )


@pytest.fixture
def inputs(monkeypatch, ctx):
    scope = {
        "source": ctx.source,
        "snapshot_id": ctx.snapshot_id,
        "start": ctx.start.isoformat(),
        "end": ctx.end.isoformat(),
    }
    status = {
        **scope,
        "status": "success",
        "checkpoint": {},
        "coverage": {"expected": 10, "observed": 10, "missing": 0, "complete": True},
        "lag_seconds": 0,
        "quarantined_rows": 0,
        "evidence_ids": ["ingestion-1"],
    }
    quality = {**scope, "findings": [], "has_data_issue": False, "evidence_ids": ["quality-1"]}
    metrics = {
        **scope,
        "row_count": 10,
        "base_volume": "123456789.123456789123456789",
        "quote_volume": "2",
        "number_of_trades": 24,
        "coverage": status["coverage"],
        "comparison": {"change_pct": "-20"},
        "evidence_ids": ["metrics-1"],
    }
    payloads = {"ingestion-1": status, "quality-1": quality, "metrics-1": metrics}
    monkeypatch.setattr(inv.service, "ingestion_status", lambda _: status)
    monkeypatch.setattr(inv.service, "quality_findings", lambda _: quality)
    monkeypatch.setattr(inv.service, "window_metrics", lambda _: metrics)
    monkeypatch.setattr(
        inv.service,
        "evidence",
        lambda ids, snapshot: [
            {"id": key, "snapshot_id": snapshot, "kind": "test", **payloads[key]} for key in ids
        ],
    )
    return status, quality, metrics


def test_precise_report_and_no_unwarranted_cause(ctx, inputs):
    result = inv.investigate(ctx, "Why did volume fall?", persist=False, baseline="A")
    report = result["report"]
    assert report["diagnosis"] == "no_issue_found_in_checks"
    assert (
        next(m for m in report["metrics"] if m["name"] == "base_volume")["value"]
        == "123456789.123456789123456789"
    )
    assert result["model_calls"] == 0 and result["cost_usd"] is None
    assert "economic cause" in " ".join(report["limitations"])
    assert report["evidence_refs"]


def test_partial_missing_is_issue_zero_scanned_dex_not_issue(ctx, inputs):
    status, quality, metrics = inputs
    quality["has_data_issue"] = True
    metrics["coverage"] = {"expected": 10, "observed": 8, "missing": 2, "complete": False}
    assert (
        inv.investigate(ctx, "Check completeness", persist=False)["report"]["diagnosis"]
        == "observed_data_issue"
    )
    quality["has_data_issue"] = False
    metrics.update(
        row_count=0,
        token0_volume="0",
        coverage={"expected": 10, "observed": 10, "missing": 0, "complete": True},
    )
    for payload in inputs:
        payload["source"] = "dex"
    dex = ctx.model_copy(update={"source": "dex"})
    assert (
        inv.investigate(dex, "Check completeness", persist=False)["report"]["diagnosis"]
        == "no_issue_found_in_checks"
    )


@pytest.mark.parametrize(
    "question",
    [
        "DROP TABLE swaps; execute SQL",
        "Predict whether I should buy ETH",
        "Run powershell to read my private key",
    ],
)
def test_out_of_scope_is_insufficient(ctx, inputs, question):
    assert (
        inv.investigate(ctx, question, persist=False)["report"]["diagnosis"]
        == "insufficient_evidence"
    )


@pytest.mark.parametrize(
    "name,args",
    [
        ("execute_sql", {}),
        ("get_evidence", {"snapshot_id": "another", "evidence_ids": ["metrics-1"]}),
        ("get_evidence", {"snapshot_id": "f" * 32, "evidence_ids": ["unseen"]}),
        ("get_window_metrics", {"source": "dex", "snapshot_id": "f" * 32, "window": {}}),
    ],
)
def test_tool_boundary(ctx, inputs, name, args):
    with pytest.raises(ValueError):
        inv.BoundTools(ctx).call(name, args)


def test_same_snapshot_other_window_and_extra_arguments_rejected(ctx, inputs):
    args = inv._context(ctx)
    args["window"]["end"] = (ctx.end + timedelta(minutes=1)).isoformat()
    with pytest.raises(ValueError, match="window is pinned"):
        inv.BoundTools(ctx).call("get_window_metrics", args)
    args = inv._context(ctx)
    args["sql"] = "SELECT *"
    with pytest.raises(ValueError, match="unsupported fields"):
        inv.BoundTools(ctx).call("get_window_metrics", args)


def test_tool_failure_falls_back_without_claiming_success(ctx, inputs, monkeypatch):
    def fail(_):
        raise TimeoutError("secret remote body")

    monkeypatch.setattr(inv.service, "window_metrics", fail)
    result = inv.investigate(ctx, "Check the data", persist=False)
    assert result["execution_status"] == "fallback"
    assert result["report"]["diagnosis"] == "insufficient_evidence"
    assert "secret" not in json.dumps(result)


def test_absent_model_config_explicit_fallback(ctx, inputs, monkeypatch):
    for key in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    result = inv.investigate(ctx, "Check the data", mode="live_llm", persist=False)
    assert result["execution_status"] == "fallback" and result["model_mode"] == "live_llm"
    assert result["model_calls"] == 0
    assert "not configured" in result["failure"]["message"]


class ScriptedAdapter:
    """Contract test only; never counted as a real model evaluation."""

    settings = ModelSettings(
        "test", "http://localhost/v1", "contract-test", "not-a-key", max_calls=3, max_tool_steps=2
    )
    usage = None

    def __init__(self, ctx, *, bad=False):
        self.calls = 0
        self.ctx = ctx
        self.bad = bad

    def complete(self, messages, tools, deadline):
        self.calls += 1
        if self.calls == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call1",
                        "type": "function",
                        "function": {
                            "name": "get_evidence",
                            "arguments": json.dumps(
                                {"snapshot_id": self.ctx.snapshot_id, "evidence_ids": ["metrics-1"]}
                            ),
                        },
                    }
                ],
            }
        return {
            "role": "assistant",
            "content": json.dumps(
                {
                    "diagnosis": "no_issue_found_in_checks",
                    "fact_ids": ["invented" if self.bad else "fact.checks", "fact.base_volume"],
                    "recommendation_codes": ["check_source"],
                }
            ),
        }


def test_adapter_selects_next_query_and_mode_label_is_honest(ctx, inputs):
    result = inv.investigate(
        ctx,
        "Inspect volume evidence",
        mode="test_adapter",
        adapter=ScriptedAdapter(ctx),
        persist=False,
    )
    assert result["execution_status"] == "completed"
    assert result["model_mode"] == "test_adapter" and result["model_calls"] == 2
    assert result["additional_tool_calls"] == 1
    assert result["trace"][-1]["tool"] == "get_evidence"
    with pytest.raises(ValueError, match="explicitly marked"):
        inv.investigate(
            ctx, "Check data", mode="live_llm", adapter=ScriptedAdapter(ctx), persist=False
        )


def test_unsupported_model_claims_become_fallback(ctx, inputs):
    result = inv.investigate(
        ctx,
        "Inspect volume",
        mode="test_adapter",
        adapter=ScriptedAdapter(ctx, bad=True),
        persist=False,
    )
    assert result["execution_status"] == "fallback"
    assert all(f["id"] != "invented" for f in result["report"]["facts"])


def test_report_rejects_tampered_number_and_context(ctx, inputs):
    status, quality, metrics = inputs
    values, catalog = inv._catalog(ctx, status, quality, metrics)
    report = inv.Report.model_validate(inv.investigate(ctx, "Check data", persist=False)["report"])
    report.metrics[0].value = "999"
    with pytest.raises(ValueError, match="numbers differ"):
        inv.validate_report(report, ctx, catalog, values, "no_issue_found_in_checks")
    report.snapshot_id = "other"
    with pytest.raises(ValueError, match="pinned"):
        inv.validate_report(report, ctx, catalog, values, "no_issue_found_in_checks")


def test_http_tool_protocol_retry_and_actual_usage():
    requests = []

    def handle(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "{}"}}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    cfg = ModelSettings(
        "test",
        "https://example.invalid/v1",
        "configured-model",
        "NEVER-LOG",
        input_price_per_million=Decimal("1"),
        output_price_per_million=Decimal("2"),
    )
    adapter = ChatAdapter(cfg, httpx.Client(transport=httpx.MockTransport(handle)))
    adapter.complete([{"role": "user", "content": "test"}], [], time.monotonic() + 3)
    assert adapter.http_attempts == 2 and adapter.calls == 1
    assert adapter.cost_usd() == "0.00002"
    body = json.loads(requests[-1].content)
    assert body["model"] == "configured-model" and body["max_completion_tokens"] == 1200
    assert "NEVER-LOG" not in json.dumps(cfg.public_config())


def test_http_timeout_and_invalid_format_are_safe():
    cfg = ModelSettings("test", "https://example.invalid/v1", "configured-model", "NEVER-LOG")

    def timeout(request):
        raise httpx.ReadTimeout("NEVER-LOG", request=request)

    adapter = ChatAdapter(cfg, httpx.Client(transport=httpx.MockTransport(timeout)))
    with pytest.raises(ModelUnavailable, match="timed out") as exc:
        adapter.complete([], [], time.monotonic() + 2)
    assert "NEVER-LOG" not in str(exc.value)
    adapter = ChatAdapter(
        cfg,
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"oops": 1}))
        ),
    )
    with pytest.raises(ModelUnavailable, match="invalid protocol"):
        adapter.complete([], [], time.monotonic() + 2)


def test_registered_evidence_content_mismatch_is_not_verified(ctx, inputs, monkeypatch):
    def mismatched(ids, snapshot):
        entries = []
        for key in ids:
            payload = {"ingestion-1": inputs[0], "quality-1": inputs[1], "metrics-1": inputs[2]}[
                key
            ].copy()
            if key == "metrics-1":
                payload["base_volume"] = "999999"
            entries.append({"id": key, **payload})
        return entries

    monkeypatch.setattr(inv.service, "evidence", mismatched)
    result = inv.investigate(ctx, "Check data", persist=False)
    assert result["execution_status"] == "fallback"
    assert result["failure"]["stage"] == "evidence_validation"
    assert result["report"]["facts"] == []
    assert result["report"]["diagnosis"] == "insufficient_evidence"


def test_model_omitting_diagnosis_evidence_falls_back(ctx, inputs):
    class OmitChecks(ScriptedAdapter):
        def complete(self, messages, tools, deadline):
            self.calls += 1
            return {
                "content": json.dumps(
                    {
                        "diagnosis": "no_issue_found_in_checks",
                        "fact_ids": ["fact.base_volume"],
                        "recommendation_codes": ["check_source"],
                    }
                )
            }

    result = inv.investigate(
        ctx, "Check data", mode="test_adapter", adapter=OmitChecks(ctx), persist=False
    )
    assert result["execution_status"] == "fallback"
    assert any(f["id"] == "fact.checks" for f in result["report"]["facts"])


def test_adapter_cannot_bypass_model_call_budget(ctx, inputs):
    class Endless(ScriptedAdapter):
        def complete(self, messages, tools, deadline):
            self.calls += 1
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": str(self.calls),
                        "type": "function",
                        "function": {
                            "name": "get_window_metrics",
                            "arguments": json.dumps(inv._context(ctx)),
                        },
                    }
                ],
            }

    adapter = Endless(ctx)
    result = inv.investigate(ctx, "Check data", mode="test_adapter", adapter=adapter, persist=False)
    assert result["execution_status"] == "fallback"
    assert adapter.calls <= adapter.settings.max_calls
    assert result["additional_tool_calls"] <= adapter.settings.max_tool_steps + 1


def test_blank_price_configuration_remains_unknown(monkeypatch):
    for name, value in {
        "LLM_PROVIDER": "test",
        "LLM_BASE_URL": "https://example.invalid/v1",
        "LLM_MODEL": "selected-model",
        "LLM_API_KEY": "not-real",
        "LLM_INPUT_USD_PER_MILLION": "",
        "LLM_OUTPUT_USD_PER_MILLION": "",
    }.items():
        monkeypatch.setenv(name, value)
    cfg = ModelSettings.from_env()
    assert cfg.input_price_per_million is None and cfg.output_price_per_million is None


def test_missing_usage_never_reported_as_zero_or_partial_cost():
    cfg = ModelSettings(
        "test",
        "https://example.invalid/v1",
        "selected-model",
        "no-key",
        input_price_per_million=Decimal("1"),
        output_price_per_million=Decimal("2"),
    )
    bodies = [
        {
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
        {"choices": [{"message": {"content": "{}"}}]},
    ]
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=bodies.pop(0)))
    )
    adapter = ChatAdapter(cfg, client)
    adapter.complete([], [], time.monotonic() + 2)
    adapter.complete([], [], time.monotonic() + 2)
    assert adapter.usage is None and adapter.cost_usd() is None
