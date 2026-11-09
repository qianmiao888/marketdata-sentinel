"""Frozen, self-authored replay benchmark; the oracle never enters agent inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
QUESTION = "Check completeness, freshness and units for this UTC window before interpreting its volume. Cite evidence and limitations."


def verify_freeze(root: Path = EVALS) -> dict:
    manifest = json.loads((root / "freeze.json").read_text(encoding="utf-8-sig"))
    for name, expected in manifest["files"].items():
        if Path(name).name != name:
            raise ValueError("Freeze entries must be local files")
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(
                f"Frozen input changed: {name}; disclose contamination and version the benchmark"
            )
    return manifest


def load_cases(split: str = "all") -> list[dict]:
    verify_freeze()
    data = json.loads((EVALS / "cases.json").read_text(encoding="utf-8-sig"))
    return [c for c in data["cases"] if split == "all" or c["split"] == split]


def _hash(value: str) -> str:
    return "0x" + hashlib.sha256(value.encode()).hexdigest()


def synthetic_input(case: dict) -> tuple[list, dict]:
    """Independent synthetic dates, not modifications of the distributed market slice.

    Recipe and oracle stay in this evaluator. Persisted raw metadata contains only
    declared source/schema/time/token information, never expected diagnosis or case ID.
    """
    start = datetime.fromisoformat(case["date"]).replace(tzinfo=UTC)
    source = case["source"]
    count = 20
    step = timedelta(minutes=1) if source == "cex" else timedelta(seconds=12)
    end = start + count * step
    manifest = {
        "source": source,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "expected_end": end.isoformat(),
        "synthetic": True,
        "mode": "snapshot replay",
        "schema_version": "evaluation-synthetic-v1",
        "raw_file": "registered database raw batch",
        "request_parameters": {"date": case["date"]},
    }
    # Date changes not only timestamps but also values; split raw fragments do not overlap.
    seed = int(start.strftime("%j"))
    if source == "cex":
        manifest.update(provider="binance", symbol="ETHUSDT", interval="1m", timestamp_unit="us")
        rows = []
        for i in range(count):
            ticks = int((start + i * step).timestamp()) * 1_000_000
            price = Decimal(2000 + seed + i)
            amount = Decimal(seed + i + 1) / 10
            if case["recipe"] == "zero_volume":
                amount = Decimal(0)
            rows.append(
                [
                    str(ticks),
                    str(price),
                    str(price + 1),
                    str(price - 1),
                    str(price),
                    str(amount),
                    str(ticks + 59_999_999),
                    str(amount * price),
                    0 if amount == 0 else i + 1,
                    "0",
                    "0",
                    "0",
                ]
            )
        return rows, manifest
    pool = "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"
    first_block = 20_000_000 + seed * 100
    blocks = [
        {
            "number": first_block + i,
            "hash": _hash(f"{start.isoformat()}:block:{i}"),
            "timestamp": (start + i * step).isoformat(),
        }
        for i in range(count)
    ]
    manifest.update(
        provider="ethereum-json-rpc",
        chain_id=1,
        pool=pool,
        token0={
            "symbol": "USDC",
            "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "decimals": 6,
        },
        token1={
            "symbol": "WETH",
            "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
            "decimals": 18,
        },
        blocks=blocks,
        request_parameters={"fromBlock": first_block, "toBlock": first_block + count - 1},
    )
    rows = [
        {
            "chain_id": 1,
            "pool": pool,
            "block_number": b["number"],
            "block_hash": b["hash"],
            "tx_hash": _hash(f"{start.isoformat()}:transaction:{i}"),
            "log_index": 0,
            "event_time": b["timestamp"],
            "amount0": str((seed + i + 1) * 1_000_000),
            "amount1": str(-(seed + i + 1) * 10**15),
        }
        for i, b in enumerate(blocks)
        if i % 3 == 0
    ]
    if case["recipe"] == "zero_swaps":
        rows = []
    return rows, manifest


def prepare_case(case: dict):
    from sentinel import pipeline, service

    rows, manifest = synthetic_input(case)
    fault = (
        case["recipe"]
        if case["recipe"] in {"missing", "stale", "invalid", "duplicate", "out_of_order"}
        else None
    )
    result = pipeline.import_snapshot(case["source"], rows, manifest, fault=fault)
    start, end = manifest["start"], manifest["end"]
    if case["recipe"] == "outside":
        start = end
        end = (datetime.fromisoformat(end) + timedelta(minutes=1)).isoformat()
    return service.Context(
        source=case["source"], snapshot_id=result["snapshot_id"], start=start, end=end
    )


def _same_number(left, right) -> bool:
    try:
        return Decimal(str(left)).is_finite() and Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, ValueError, TypeError):
        return False


def _contains_pair(value, key: str, expected) -> bool:
    if isinstance(value, dict):
        if key in value and (value[key] == expected or _same_number(value[key], expected)):
            return True
        return any(_contains_pair(v, key, expected) for v in value.values())
    if isinstance(value, list):
        return any(_contains_pair(v, key, expected) for v in value)
    return False


def score_report(case: dict, result: dict, ctx, truth: dict) -> dict:
    """Mechanical fact checks; semantic review remains explicitly manual."""
    from sentinel import service

    report = result["report"]
    metrics = report.get("metrics", [])
    expected = dict(truth["metrics"])
    coverage = truth["metrics"].get("coverage", truth["status"].get("coverage", {}))
    expected.update({"coverage_" + k: v for k, v in coverage.items()})
    expected.update({k: truth["status"].get(k) for k in ("lag_seconds", "quarantined_rows")})
    expected["change_pct"] = truth["metrics"].get("comparison", {}).get("change_pct")
    correct_metrics = {
        m["id"]
        for m in metrics
        if m.get("name") in expected and _same_number(m.get("value"), expected[m["name"]])
    }
    numeric = {"numerator": len(correct_metrics), "denominator": len(metrics)}
    try:
        evidence = (
            {e["id"]: e for e in service.evidence(report.get("evidence_refs", []), ctx.snapshot_id)}
            if report.get("evidence_refs")
            else {}
        )
    except (ValueError, TypeError):
        evidence = {}
    by_metric = {m["id"]: m for m in metrics}
    supported = 0
    claims = report.get("facts", [])
    labels = {
        "row_count": "Observed records",
        "base_volume": "CEX base volume",
        "quote_volume": "CEX quote volume",
        "number_of_trades": "Source-reported trades",
        "token0_volume": "DEX absolute token0 amount",
        "lag_seconds": "Data lag",
        "quarantined_rows": "Quarantined records in query window",
        "change_pct": "Volume change awaiting investigation",
        **{"coverage_" + k: "Coverage " + k for k in ("expected", "observed", "missing")},
    }
    for fact in claims:
        refs = fact.get("evidence_refs", [])
        valid = bool(refs) and all(e in evidence for e in refs)
        valid = valid and all(
            evidence[e].get("source") == ctx.source
            and evidence[e].get("snapshot_id") == ctx.snapshot_id
            and evidence[e].get("start") == ctx.start.isoformat()
            and evidence[e].get("end") == ctx.end.isoformat()
            for e in refs
            if e in evidence
        )
        metric_refs = fact.get("metric_refs", [])
        if metric_refs:
            for mid in metric_refs:
                metric = by_metric.get(mid, {})
                key = metric.get("name", "")
                if key.startswith("coverage_"):
                    key = key.removeprefix("coverage_")
                valid = (
                    valid
                    and mid in correct_metrics
                    and set(metric.get("evidence_ids", [])).issubset(refs)
                )
                valid = valid and any(
                    _contains_pair(evidence[e], key, metric.get("value"))
                    for e in refs
                    if e in evidence
                )
                # Displayed numbers and claim wording must match their registered metric.
                label = labels.get(metric.get("name"))
                valid = (
                    valid
                    and label is not None
                    and fact.get("statement")
                    == f"{label}: {metric.get('value')} {metric.get('unit')}."
                )
        elif fact.get("id", "").startswith("fact.quality."):
            match = re.fullmatch(r"Quality rule (.+) returned (.+)\.", fact.get("statement", ""))
            valid = valid and bool(match)
            if match:
                valid = valid and any(
                    _contains_pair(evidence[e], "rule", match[1])
                    and _contains_pair(evidence[e], "severity", match[2])
                    for e in refs
                    if e in evidence
                )
        elif fact.get("id") == "fact.checks":
            issue = truth["quality"].get("has_data_issue")
            expected_statement = (
                "Implemented quality checks observed a data issue."
                if issue
                else "Implemented checks could not establish window-specific data quality because evidence has unresolved time coverage."
                if truth["quality"].get("has_unresolved_evidence")
                else "Implemented quality checks did not find a data issue; this is not proof of absolute correctness."
            )
            valid = (
                valid
                and fact.get("statement") == expected_statement
                and any(
                    _contains_pair(evidence[e], "has_data_issue", issue)
                    for e in refs
                    if e in evidence
                )
            )
            if truth["quality"].get("has_unresolved_evidence") and not issue:
                valid = valid and any(
                    _contains_pair(evidence[e], "has_unresolved_evidence", True)
                    for e in refs
                    if e in evidence
                )
        elif fact.get("id") != "fact.available":
            valid = False
        supported += int(bool(valid))
    scope_ok = report.get("source") == ctx.source and report.get("snapshot_id") == ctx.snapshot_id
    scope_ok = scope_ok and report.get("window") == {
        "start": ctx.start.isoformat(),
        "end": ctx.end.isoformat(),
    }
    diagnosis_ok = report.get("diagnosis") == case["expected"] and scope_ok
    insufficient = case["category"] == "insufficient"
    unknown_ok = report.get("diagnosis") == "insufficient_evidence" and bool(
        report.get("limitations")
    )
    return {
        "diagnosis": {"numerator": int(diagnosis_ok), "denominator": 1},
        "numeric": numeric,
        "evidence": {"numerator": supported, "denominator": len(claims)},
        "unknown_handling": {
            "numerator": int(unknown_ok) if insufficient else 0,
            "denominator": int(insufficient),
        },
        "success": diagnosis_ok
        and numeric["numerator"] == numeric["denominator"]
        and supported == len(claims),
        "manual_review": "PENDING: scope of advice, limitations, economic-cause restraint and clarity",
    }


def model_completed(result: dict) -> bool:
    """A fallback, a test adapter, or a failed/zero-call attempt is never live completion."""
    return (
        result.get("model_mode") == "live_llm"
        and result.get("actual_model_mode") == "live_llm"
        and result.get("execution_status") == "completed"
        and not result.get("failure")
        and result.get("model_calls", 0) > 0
    )


def summarize(results: list[dict], baseline="A") -> dict:
    groups = defaultdict(
        lambda: {
            k: {"numerator": 0, "denominator": 0}
            for k in (
                "diagnosis",
                "numeric",
                "evidence",
                "unknown_handling",
                "success",
                "system_report_accuracy",
                "model_completion_rate",
                "model_accuracy",
                "completed_model_accuracy",
            )
        }
    )
    for row in results:
        for group in ("all", row["category"]):
            for key in ("diagnosis", "numeric", "evidence", "unknown_handling"):
                for component in ("numerator", "denominator"):
                    groups[group][key][component] += row["score"][key][component]
            groups[group]["success"]["numerator"] += int(row["score"]["success"])
            groups[group]["success"]["denominator"] += 1
            correct = bool(row["score"]["success"])
            groups[group]["system_report_accuracy"]["numerator"] += int(correct)
            groups[group]["system_report_accuracy"]["denominator"] += 1
            if baseline in {"B", "C"}:
                completed = model_completed(row.get("result", {}))
                for key, numerator, denominator in (
                    ("model_completion_rate", completed, 1),
                    ("model_accuracy", completed and correct, 1),
                    ("completed_model_accuracy", completed and correct, completed),
                ):
                    groups[group][key]["numerator"] += int(numerator)
                    groups[group][key]["denominator"] += int(denominator)
    return dict(groups)


def run_evaluation(split="all", baseline="A", live=False, output: Path | None = None) -> dict:
    from sentinel import db, investigation, service

    target = (
        output
        or EVALS
        / "results"
        / "correctness-v2"
        / f"{baseline}-{split}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    if target.suffix != ".json":
        raise ValueError("Evaluation output must end in .json")
    if target.exists() or target.with_suffix(".md").exists():
        raise ValueError(
            "Evaluation output already exists; choose a new path to preserve previous results"
        )
    freeze = verify_freeze()
    cases = load_cases(split)
    artifact = {
        "created_at": datetime.now(UTC).isoformat(),
        "benchmark_version": "v1",
        "scoring_version": "correctness-v2",
        "product_scope": "Rule diagnosis + model evidence organization",
        "implementation_files_sha256": {
            str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                ROOT / "sentinel" / name
                for name in (
                    "evaluation.py",
                    "pipeline.py",
                    "service.py",
                    "investigation.py",
                    "llm.py",
                )
            ]
            + [ROOT / "uv.lock"]
        },
        "planned_cases": len(cases),
        "freeze": freeze,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "backend": "postgresql"
            if os.getenv("DATABASE_URL", "").startswith("postgresql")
            else "sqlite",
        },
        "split": split,
        "baseline": baseline,
        "data_kind": "synthetic",
        "manual_review_status": "PENDING",
        "limitations": [
            "Self-authored, sixteen cases; forty-case target not reached.",
            "Automated factual checks do not replace human semantic review.",
        ],
    }
    not_run_reason = (
        "Real model baseline requires --live and explicit model configuration"
        if baseline in {"B", "C"} and not live
        else None
    )
    if baseline in {"B", "C"} and live:
        from sentinel.llm import ModelSettings

        try:
            ModelSettings.from_env()
        except Exception:
            not_run_reason = "Model configuration unavailable; no cases attempted"
    if not_run_reason:
        artifact.update(
            status="NOT RUN",
            reason=not_run_reason,
            results=[],
            summary={},
        )
    else:
        db.init_db()
        results = []
        for case in cases:
            started = time.monotonic()
            ctx = prepare_case(case)
            truth = {}
            for name, operation in (
                ("metrics", service.window_metrics),
                ("status", service.ingestion_status),
                ("quality", service.quality_findings),
            ):
                try:
                    truth[name] = operation(ctx)
                except ValueError:
                    truth[name] = {}
            try:
                result = investigation.investigate(
                    ctx,
                    QUESTION,
                    mode="deterministic" if baseline == "A" else "live_llm",
                    baseline=baseline,
                )
                score = score_report(case, result, ctx, truth)
                row = {
                    "case_id": case["id"],
                    "split": case["split"],
                    "category": case["category"],
                    "snapshot_id": ctx.snapshot_id,
                    "score": score,
                    "result": result,
                }
            except Exception as exc:
                row = {
                    "case_id": case["id"],
                    "split": case["split"],
                    "category": case["category"],
                    "snapshot_id": ctx.snapshot_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "score": {
                        k: {
                            "numerator": 0,
                            "denominator": 1
                            if k != "unknown_handling"
                            else int(case["category"] == "insufficient"),
                        }
                        for k in ("diagnosis", "numeric", "evidence", "unknown_handling")
                    },
                }
                row["score"]["success"] = False
            row["observed_latency_ms"] = round((time.monotonic() - started) * 1000, 3)
            results.append(row)
        artifact.update(
            status="EXECUTED",
            results=results,
            summary=summarize(results, baseline=baseline),
            failures=[r["case_id"] for r in results if not r["score"]["success"]],
            model_failures=[
                r["case_id"]
                for r in results
                if not model_completed(r.get("result", {})) or not r["score"]["success"]
            ]
            if baseline in {"B", "C"}
            else [],
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, indent=2, default=str) + "\n", encoding="utf-8")
    table = [
        f"# Evaluation {baseline} / {split}",
        "",
        f"Status: {artifact['status']}; generated {artifact['created_at']}.",
        "",
        "Product scope: rule diagnosis + model evidence organization. System scores include template fallback; model scores exclude fallback success.",
        "",
        "| Group | System diagnosis | Numbers | Evidence support | Unknown handling | System report correct | Model completed / attempted | Model correct / attempted | Model correct / completed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, group in artifact["summary"].items():
        table.append(
            "| "
            + name
            + " | "
            + " | ".join(
                f"{group[k]['numerator']}/{group[k]['denominator']}"
                for k in (
                    "diagnosis",
                    "numeric",
                    "evidence",
                    "unknown_handling",
                    "system_report_accuracy",
                    "model_completion_rate",
                    "model_accuracy",
                    "completed_model_accuracy",
                )
            )
            + " |"
        )
    if artifact["status"] == "NOT RUN":
        table.extend(["", artifact["reason"]])
    else:
        table.extend(
            [
                "",
                "Failed cases: " + (", ".join(artifact["failures"]) or "none"),
                "Model failed/incorrect cases (including fallback): "
                + (", ".join(artifact["model_failures"]) or "none / not applicable"),
                "Model ratios 0/0 mean NOT APPLICABLE or NOT RUN, never a zero-cost/zero-error model success.",
                "",
                "Human semantic review: PENDING. Unknown token/fee fields remain null in the JSON artifact.",
            ]
        )
    target.with_suffix(".md").write_text("\n".join(table) + "\n", encoding="utf-8")
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["all", "development", "acceptance"], default="all")
    parser.add_argument("--baseline", choices=["A", "B", "C"], default="A")
    parser.add_argument(
        "--live", action="store_true", help="Explicitly enable real provider calls for B/C"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_evaluation(args.split, args.baseline, args.live, args.output)
    print(
        json.dumps(
            {k: result.get(k) for k in ("status", "baseline", "split", "summary", "failures")},
            indent=2,
        )
    )
    return int(bool(result.get("failures") or result.get("model_failures")))


if __name__ == "__main__":
    raise SystemExit(main())
