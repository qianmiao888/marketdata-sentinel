"""Deterministic business deliverables from persisted, evidence-validated reports."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from sentinel import db, investigation, pipeline, service
from sentinel.models import Evidence, Snapshot

JUDGMENTS = {
    "observed_data_issue": (
        "发现数据问题：不能将当前数字直接作为完整窗口的成交数量引用。",
        "Data issue observed: do not cite this value as the complete-window quantity.",
    ),
    "no_issue_found_in_checks": (
        "已执行检查未发现问题：引用时仍需保留来源、窗口、版本与单位，并完成校审。",
        "No issue found in executed checks: retain source, window, version and unit, and review before use.",
    ),
    "insufficient_evidence": (
        "证据不足或检查失败：当前不足以判断，暂缓对外引用。",
        "Insufficient evidence or failed checks: withhold external citation pending investigation.",
    ),
}

LABELS = {
    "row_count": ("观测记录", "Observed records"),
    "base_volume": ("基础资产成交数量", "Base-asset quantity"),
    "quote_volume": ("计价资产成交数量", "Quote-asset quantity"),
    "token0_volume": ("Token0 单侧绝对数量", "Token0 single-side absolute quantity"),
    "number_of_trades": ("来源记录的成交笔数", "Source-reported trades"),
    "coverage_expected": ("预期覆盖", "Expected coverage"),
    "coverage_observed": ("实际覆盖", "Observed coverage"),
    "coverage_missing": ("缺失覆盖", "Missing coverage"),
    "lag_seconds": ("相对参考时钟的延迟", "Lag relative to reference clock"),
    "quarantined_rows": ("窗口内隔离记录", "Quarantined rows in window"),
    "change_pct": (
        "相邻子窗口变化（待调查）",
        "Adjacent-subwindow change (requires investigation)",
    ),
}


EXECUTION_LABELS = {
    "completed": ("重放已完成", "Replay completed"),
    "not_run": ("未执行", "Not run"),
    "failed": ("执行失败", "Failed"),
    "unresolved": ("仍有问题或证据不足", "Unresolved or insufficient evidence"),
    "no_issue_found_in_checks": ("已执行检查未发现问题", "No issue found in executed checks"),
    "observed_data_issue": ("发现数据问题", "Data issue observed"),
    "insufficient_evidence": ("证据不足", "Insufficient evidence"),
}

BUSINESS_METRICS = {
    "row_count",
    "base_volume",
    "quote_volume",
    "token0_volume",
    "coverage_expected",
    "coverage_observed",
    "coverage_missing",
}


def execution_label(value, english=False):
    return EXECUTION_LABELS.get(value, ("未知", "Unknown"))[int(english)]


class CommunicationBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "communication-v1"
    status: str = "draft_requires_review"
    run_id: str
    created_at: str
    context: dict
    provenance: dict
    report: dict
    metrics: list[dict]
    evidence: list[dict]
    recovery: dict | None
    comparison: dict | None
    judgment_zh: str
    judgment_en: str
    markdown_zh: str = ""
    markdown_en: str = ""
    issue_markdown: str = ""


def report_context(result):
    report = result["report"]
    return service.Context(
        source=report["source"], snapshot_id=report["snapshot_id"], **report["window"]
    )


def verified_run(run_id):
    """Revalidate frozen evidence, never silently replace it with current queries."""
    result = investigation.get_run(run_id)
    report = investigation.Report.model_validate(result["report"])
    ctx = report_context(result)
    evidence = service.evidence(report.evidence_refs, ctx.snapshot_id)
    for item in evidence:
        payload = {key: value for key, value in item.items() if key not in {"id", "kind"}}
        expected_id = "e-" + pipeline.digest({"kind": item["kind"], "payload": payload})[:32]
        if item["id"] != expected_id:
            raise ValueError("Registered evidence content checksum mismatch")
        if item.get("source") != ctx.source or not (
            investigation._iso_equal(item.get("start", ""), ctx.start.isoformat())
            and investigation._iso_equal(item.get("end", ""), ctx.end.isoformat())
        ):
            raise ValueError("Stored report evidence has mismatched scope")
    kinds = {item["kind"]: item for item in evidence}
    initial = {
        key: deepcopy(kinds.get(kind, {}))
        for key, kind in (
            ("status", "ingestion_status"),
            ("quality", "quality_findings"),
            ("metrics", "window_metrics"),
        )
    }
    # Reconstruct internal references on independent copies; exported registered evidence
    # must retain the exact payload that produced its content-addressed ID.
    for payload in initial.values():
        if payload:
            payload["evidence_ids"] = [payload["id"]] + [
                eid for finding in payload.get("findings", []) for eid in finding["evidence_ids"]
            ]
    metrics, catalog = investigation._catalog(ctx, **initial)
    expected = investigation._diagnosis(report.question, **initial)
    if (result.get("failure") or {}).get("stage") in {"initial_tools", "evidence_validation"}:
        expected = "insufficient_evidence"
    investigation.validate_report(report, ctx, catalog, metrics, expected)
    return result, evidence


def provenance(ctx):
    with db.SessionLocal() as session:
        snap = session.get(Snapshot, ctx.snapshot_id)
        if snap is None or snap.source != ctx.source:
            raise ValueError("Report source version unavailable")
        manifest = snap.manifest
        return {
            key: manifest.get(key)
            for key in (
                "provider",
                "symbol",
                "interval",
                "chain_id",
                "pool",
                "mode",
                "synthetic",
                "transform",
                "checksum",
                "input_checksum",
                "provenance",
            )
        }


def recover(before_run_id):
    before, _ = verified_run(before_run_id)
    ctx = report_context(before)
    receipt = {
        "id": "recovery-" + uuid4().hex,
        "created_at": datetime.now(UTC).isoformat(),
        "source": ctx.source,
        "snapshot_id": ctx.snapshot_id,
        "start": ctx.start.isoformat(),
        "end": ctx.end.isoformat(),
        "before_run_id": before_run_id,
        "after_run_id": None,
        "restored_snapshot_id": None,
        "action": "replay_registered_raw_input",
        "restore_status": "not_run",
        "verification_status": "not_run",
        "error": None,
    }
    try:
        restored = pipeline.restore(ctx.snapshot_id)
        receipt["restore_status"] = "completed"
        receipt["restored_snapshot_id"] = restored["snapshot_id"]
        after_ctx = ctx.model_copy(update={"snapshot_id": restored["snapshot_id"]})
        if provenance(ctx)["input_checksum"] != provenance(after_ctx)["input_checksum"]:
            raise ValueError("Recovery input lineage differs")
        after = investigation.investigate(
            after_ctx, before["report"]["question"], mode="deterministic", baseline="A"
        )
        receipt["after_run_id"] = after["run_id"]
        receipt["verification_status"] = (
            "no_issue_found_in_checks"
            if after["report"]["diagnosis"] == "no_issue_found_in_checks" and not after["failure"]
            else "unresolved"
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("Recovery stage failed: %s", type(exc).__name__)
        if receipt["restore_status"] == "not_run":
            receipt["restore_status"] = "failed"
        receipt["verification_status"] = "failed"
        receipt["error"] = (
            "恢复或恢复后核验失败；保留原报告，请检查本地服务日志。 / Recovery or verification failed."
        )
    with db.SessionLocal() as session:
        session.add(
            Evidence(
                id=receipt["id"],
                snapshot_id=ctx.snapshot_id,
                kind="recovery_result",
                payload=receipt,
            )
        )
        session.commit()
    return receipt


def _recovery(receipt_id, run_id):
    with db.SessionLocal() as session:
        row = session.get(Evidence, receipt_id)
        if row is None or row.kind != "recovery_result":
            raise ValueError("Unknown recovery record")
        receipt = dict(row.payload)
    if run_id not in {receipt["before_run_id"], receipt["after_run_id"]}:
        raise ValueError("Recovery is not associated with this report")
    before, _ = verified_run(receipt["before_run_id"])
    before_ctx = report_context(before)
    if not (
        receipt["source"] == before_ctx.source
        and receipt["snapshot_id"] == before_ctx.snapshot_id
        and investigation._iso_equal(receipt["start"], before_ctx.start.isoformat())
        and investigation._iso_equal(receipt["end"], before_ctx.end.isoformat())
    ):
        raise ValueError("Recovery scope mismatch")
    versions = []
    for role, report_id in (
        ("before", receipt["before_run_id"]),
        ("after", receipt["after_run_id"]),
    ):
        if report_id is None:
            continue
        result, evidence = verified_run(report_id)
        ctx = report_context(result)
        if (
            ctx.source != before_ctx.source
            or ctx.start != before_ctx.start
            or ctx.end != before_ctx.end
        ):
            raise ValueError("Comparison requires identical source and window")
        if role == "after" and ctx.snapshot_id != receipt["restored_snapshot_id"]:
            raise ValueError("Recovered version mismatch")
        versions.append(
            {
                "role": role,
                "run_id": report_id,
                "report": result["report"],
                "evidence": evidence,
                "provenance": provenance(ctx),
            }
        )
    return receipt, {"versions": versions, "meaning": "same_window_versions_not_market_change"}


def build_bundle(run_id, recovery_id=None):
    result, evidence = verified_run(run_id)
    ctx = report_context(result)
    report = result["report"]
    receipt, comparison = _recovery(recovery_id, run_id) if recovery_id else (None, None)
    zh, en = JUDGMENTS[report["diagnosis"]]
    bundle = CommunicationBundle(
        run_id=run_id,
        created_at=result["created_at"],
        context=ctx.model_dump(mode="json"),
        provenance=provenance(ctx),
        report=report,
        metrics=report["metrics"],
        evidence=evidence,
        recovery=receipt,
        comparison=comparison,
        judgment_zh=zh,
        judgment_en=en,
    )
    bundle.markdown_zh = render_markdown(bundle, "zh")
    bundle.markdown_en = render_markdown(bundle, "en")
    bundle.issue_markdown = render_issue(bundle)
    return bundle.model_dump()


def data_notice(prov, english=False):
    if prov.get("synthetic") is not False:
        return (
            "Synthetic replay; not verified real on-chain ingestion."
            if english
            else "合成数据回放；不代表已验证真实链上采集。"
        )
    if prov.get("transform"):
        return (
            "Public historical data with a deliberately injected fault; this is not an exchange incident."
            if english
            else "真实公开历史数据，人为构造的故障演练；不是交易所真实事故。"
        )
    return (
        "Public historical data; not a real-time feed."
        if english
        else "真实公开历史数据；不是实时行情。"
    )


def metric_table(metrics, english=False):
    metrics = [metric for metric in metrics if metric["name"] in BUSINESS_METRICS]
    rows = [
        "| Metric | Exact value | Unit | Evidence |"
        if english
        else "| 指标 | 精确原值 | 单位 | 证据 |",
        "|---|---|---|---|",
    ]
    for metric in metrics:
        label = LABELS.get(metric["name"], (metric["name"], metric["name"]))[int(english)]
        rows.append(
            f"| {label} | {metric['value']} | {metric['unit']} | {', '.join(metric['evidence_ids'])} |"
        )
    if not metrics:
        rows.append("| Unknown / 未知 | — | — | Insufficient evidence / 证据不足 |")
    return "\n".join(rows)


def render_markdown(bundle, language):
    en = language == "en"
    ctx = bundle.context
    report = bundle.report
    parts = [
        "# MarketData Sentinel · User communication draft"
        if en
        else "# MarketData Sentinel · 用户说明草稿",
        "DRAFT · Human editorial review pending. Not approved for publication."
        if en
        else "草稿 · 待人工校审，尚未批准对外发布。",
        f"Report / 报告：`{bundle.run_id}` · {bundle.created_at}",
        ("## User question" if en else "## 用户问题") + "\n" + report["question"],
        ("## Current judgment" if en else "## 当前判断")
        + "\n"
        + (bundle.judgment_en if en else bundle.judgment_zh),
        data_notice(bundle.provenance, en),
        f"Source / 来源：{ctx['source']} · {bundle.provenance.get('symbol') or bundle.provenance.get('pool') or 'unknown'}\n\nVersion / 版本：`{ctx['snapshot_id']}`\n\nUTC [{ctx['start']}, {ctx['end']})",
        ("## Key figures and evidence" if en else "## 关键数字与证据")
        + "\n"
        + metric_table(bundle.metrics, en),
    ]
    origin = bundle.provenance.get("provenance") or {}
    if origin.get("url"):
        parts.append(f"Original source / 原始来源：{origin['url']}")
    parts.append(
        f"Input checksum / 输入校验值：`{bundle.provenance.get('input_checksum') or 'unknown'}`"
    )
    parts.append(
        "Additional exact metrics and full evidence are retained in the structured JSON export."
        if en
        else "其他精确指标与完整证据保留在结构化 JSON 导出中。"
    )
    parts.append("## Actual handling and verification" if en else "## 实际处理与验证")
    if bundle.recovery:
        rec = bundle.recovery
        parts.append(
            f"Recovery / 恢复记录：`{rec['id']}`\n\nReplay / 重放：{execution_label(rec['restore_status'], en)} · Verification / 核验：{execution_label(rec['verification_status'], en)}"
        )
        if rec["error"]:
            parts.append(rec["error"])
        for version in bundle.comparison["versions"]:
            parts.append(
                f"### {version['role']} · `{version['report']['snapshot_id']}`\n\nReport / 报告：`{version['run_id']}`\n\n"
                + metric_table(version["report"]["metrics"], en)
            )
        parts.append(
            "These are versions of the same window, not market growth or decline."
            if en
            else "这是同一时间窗口的数据版本对照，不能解释为市场涨跌。"
        )
        parts.append(data_notice(bundle.comparison["versions"][0]["provenance"], en))
    else:
        parts.append(
            "The bound report executed data checks; no recovery record is attached. Recovery is not claimed."
            if en
            else "已执行绑定报告中的数据检查；未关联恢复记录，不宣称已完成恢复。"
        )
    parts.extend(
        [
            "## Uncertainty and next steps" if en else "## 不确定性与下一步",
            "Only implemented checks were evaluated; passing them does not rule out all errors or establish a market cause. Verify the source and editorial context before citation. Human usability validation is pending."
            if en
            else "仅执行已实现的检查；通过不代表排除全部错误，也不证明市场因果。引用前继续核对来源与使用语境，完成数字、单位、遗漏、因果及确定程度的双语校审。真人使用验证待完成。",
            "\n".join(f"- {item}" for item in report["limitations"]),
            (
                "Next checks / 下一步：\n"
                + "\n".join(f"- {item}" for item in report["recommendations"])
            ),
        ]
    )
    return "\n\n".join(parts) + "\n"


def render_issue(bundle):
    ctx = bundle.context
    rec = bundle.recovery
    return (
        "\n\n".join(
            [
                f"# 问题单 · {bundle.run_id}",
                "状态：草稿待校审；真人使用验证待完成。",
                f"## 现象\n{bundle.report['question']}",
                f"## 当前判断\n{bundle.judgment_zh}",
                f"## 已知影响范围\n仅限来源 {ctx['source']}、版本 `{ctx['snapshot_id']}`、UTC [{ctx['start']}, {ctx['end']})；不外推至整个交易所或市场。",
                "## 复现步骤\n1. 启动工作台并选择上述来源、版本和 UTC 窗口。\n2. 运行数据检查，查看覆盖情况及登记证据。\n3. 如需复现恢复，点击从原始输入恢复，保持相同时间窗，再对照报告。",
                "## 实际处理与验证\n"
                + (
                    f"记录 `{rec['id']}`；重放：{execution_label(rec['restore_status'])}；核验：{execution_label(rec['verification_status'])}。"
                    if rec
                    else "数据检查已执行；恢复未关联，不标记完成。"
                ),
                "## 证据\n" + metric_table(bundle.metrics),
                "## 待解决项\n人工内容校审待完成；真人使用验证待完成；检查范围以外的数据错误和市场原因尚未排除。",
                "## 用户说明\n" + bundle.markdown_zh,
            ]
        )
        + "\n"
    )
