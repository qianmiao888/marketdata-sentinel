from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from sentinel.db import SessionLocal
from sentinel.models import (
    Candle,
    Coverage,
    Evidence,
    IngestionRun,
    QualityFinding,
    Quarantine,
    RawBatch,
    Snapshot,
    Swap,
)
from sentinel.pipeline import digest, iso, row_event_time, utc


class Context(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["cex", "dex"]
    snapshot_id: str = Field(min_length=1, max_length=80)
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("timezone-aware UTC bounds required")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def window(self):
        if self.end <= self.start or self.end - self.start > timedelta(days=7):
            raise ValueError("window must be positive and at most 7 days")
        if self.source == "cex" and (
            self.start.second or self.start.microsecond or self.end.second or self.end.microsecond
        ):
            raise ValueError("CEX query boundaries must be minute aligned")
        return self


def _context(ctx):
    return {
        "source": ctx.source,
        "snapshot_id": ctx.snapshot_id,
        "start": iso(ctx.start),
        "end": iso(ctx.end),
    }


def _snapshot(session, ctx):
    snap = session.get(Snapshot, ctx.snapshot_id)
    if snap is None or snap.source != ctx.source:
        raise ValueError("snapshot not found for bound source")
    return snap


def _register(session, ctx, kind, payload):
    flat = {**_context(ctx), **payload}
    eid = "e-" + digest({"kind": kind, "payload": flat})[:32]
    if session.get(Evidence, eid) is None:
        session.add(Evidence(id=eid, snapshot_id=ctx.snapshot_id, kind=kind, payload=flat))
    return eid


def _rows(session, ctx):
    model = Candle if ctx.source == "cex" else Swap
    time = model.open_time if ctx.source == "cex" else model.event_time
    return list(
        session.scalars(
            select(model)
            .where(model.snapshot_id == ctx.snapshot_id, time >= ctx.start, time < ctx.end)
            .order_by(time)
        )
    )


def _dex_intervals(ctx, manifest):
    """A block covers [its timestamp, next pinned timestamp), including empty slots."""
    blocks = sorted(manifest.get("blocks", []), key=lambda b: b["number"])
    intervals = []
    for i, block in enumerate(blocks):
        start = utc(block["timestamp"])
        end = utc(blocks[i + 1]["timestamp"]) if i + 1 < len(blocks) else utc(manifest["end"])
        if end <= start:
            raise ValueError("Pinned block times must be strictly increasing")
        if start < ctx.end and end > ctx.start:
            intervals.append((block, start, end))
    return intervals


def _scanned_blocks(session, ctx, intervals):
    expected = {b["number"]: b["hash"] for b, _, _ in intervals}
    return {
        b.block_number
        for b in session.scalars(
            select(Coverage).where(
                Coverage.snapshot_id == ctx.snapshot_id, Coverage.block_number.in_(expected)
            )
        )
        if b.block_hash == expected[b.block_number]
    }


def _quarantine_scope(session, ctx, snap):
    groups = {"in_window": [], "outside_window": [], "unknown_time": []}
    for q in session.scalars(select(Quarantine).where(Quarantine.snapshot_id == ctx.snapshot_id)):
        event, basis = row_event_time(ctx.source, q.raw["row"], snap.manifest)
        group = (
            "unknown_time"
            if event is None
            else "in_window"
            if ctx.start <= utc(event) < ctx.end
            else "outside_window"
        )
        groups[group].append(
            {
                "id": q.id,
                "raw_batch_id": q.raw_batch_id,
                "row_index": q.row_index,
                "reason": q.reason,
                "event_time": event,
                "time_basis": basis,
                "row": q.raw["row"],
            }
        )
    return groups


def _observations(session, ctx, kind):
    return [
        {"observation_id": r.id, **r.payload}
        for r in session.scalars(
            select(Evidence).where(Evidence.snapshot_id == ctx.snapshot_id, Evidence.kind == kind)
        )
        if r.payload.get("event_time") is not None
        and ctx.start <= utc(r.payload["event_time"]) < ctx.end
    ]


def _coverage(session, ctx, snap):
    manifest = snap.manifest
    contained = utc(manifest["start"]) <= ctx.start and ctx.end <= utc(manifest["end"])
    known = True
    if ctx.source == "cex":
        expected = int((ctx.end - ctx.start).total_seconds() // 60)
        times = {iso(x.open_time) for x in _rows(session, ctx)}
        missing = [
            iso(ctx.start + timedelta(minutes=i))
            for i in range(expected)
            if iso(ctx.start + timedelta(minutes=i)) not in times
        ]
        observed = expected - len(missing)
    else:
        intervals = _dex_intervals(ctx, manifest)
        expected = len(intervals)
        scanned = _scanned_blocks(session, ctx, intervals)
        missing = [b["number"] for b, _, _ in intervals if b["number"] not in scanned]
        observed = expected - len(missing)
        # A declared range without a block anchor cannot establish empty-window coverage.
        known = bool(intervals) and intervals[0][1] <= ctx.start and intervals[-1][2] >= ctx.end
    return {
        "expected": expected,
        "observed": observed,
        "missing": len(missing),
        "missing_items": missing[:100],
        "complete": contained and known and not missing,
        "coverage_known": known,
        "window_covered": contained,
        "unit": "candles" if ctx.source == "cex" else "scanned_blocks",
    }


def _lag(session, ctx, snap):
    # Replay clock is frozen at expected_end. Connected daily archives allow one day publication delay.
    if snap.manifest.get("mode") == "connected collection":
        reference = datetime.now(timezone.utc) - timedelta(
            seconds=int(
                snap.manifest.get("publication_delay_seconds", 86400 if ctx.source == "cex" else 0)
            )
        )
        reference = min(reference, utc(snap.manifest["expected_end"]))
    else:
        reference = utc(snap.manifest.get("expected_end", snap.manifest["end"]))
    reference = min(reference, ctx.end)
    if ctx.source == "cex":
        rows = _rows(session, ctx)
        actual = max(
            (utc(iso(r.open_time)) + timedelta(minutes=1) for r in rows), default=ctx.start
        )
    else:
        intervals = _dex_intervals(ctx, snap.manifest)
        if not intervals or intervals[0][1] > ctx.start or intervals[-1][2] < ctx.end:
            return None
        scanned = _scanned_blocks(session, ctx, intervals)
        actual = max(
            (min(end, ctx.end) for b, _, end in intervals if b["number"] in scanned),
            default=ctx.start,
        )
    return max(0, int((reference - actual).total_seconds()))


def sources():
    return [
        {
            "id": "cex",
            "name": "Binance ETHUSDT spot 1m",
            "base_unit": "ETH",
            "quote_unit": "USDT",
            "granularity": "1 minute",
            "mode": "snapshot replay / connected collection",
        },
        {
            "id": "dex",
            "name": "Ethereum Uniswap v3 USDC/WETH 0.3%",
            "chain_id": 1,
            "pool": "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8",
            "volume_unit": "USDC token0 single-side absolute quantity",
            "mode": "snapshot replay / connected collection",
        },
    ]


def list_snapshots():
    with SessionLocal() as session:
        return [
            {
                "id": s.id,
                "snapshot_id": s.id,
                "source": s.source,
                "start": s.manifest["start"],
                "end": s.manifest["end"],
                "mode": s.manifest.get("mode", "snapshot replay"),
                "synthetic": s.manifest.get("synthetic", True),
                "transform": s.manifest.get("transform"),
                "created_at": iso(s.created_at),
                "input_checksum": s.manifest["input_checksum"],
            }
            for s in session.scalars(select(Snapshot).order_by(Snapshot.created_at))
        ]


def ingestion_status(ctx):
    with SessionLocal() as session:
        snap = _snapshot(session, ctx)
        runs = list(
            session.scalars(
                select(IngestionRun)
                .where(IngestionRun.snapshot_id == ctx.snapshot_id)
                .order_by(IngestionRun.created_at.desc())
            )
        )
        quarantines = _quarantine_scope(session, ctx, snap)
        run = runs[0] if runs else None
        successes = [r for r in runs if r.status == "success"]
        result = {
            **_context(ctx),
            "status": run.status if run else "not_run",
            "checkpoint": run.checkpoint if run else {},
            "last_success_at": iso(successes[0].created_at) if successes else None,
            "lag_seconds": _lag(session, ctx, snap),
            "quarantined_rows": len(quarantines["in_window"]),
            "quarantine_scope": {k: len(v) for k, v in quarantines.items()},
            "quarantined_rows_total": sum(len(v) for v in quarantines.values()),
            "identical_duplicates": len(_observations(session, ctx, "record_duplicate")),
            "record_conflicts": len(_observations(session, ctx, "record_conflict")),
            "coverage": _coverage(session, ctx, snap),
            "mode": snap.manifest.get("mode", "snapshot replay"),
            "synthetic": snap.manifest["synthetic"],
            "schema_version": snap.manifest["schema_version"],
            "input_checksum": snap.manifest["input_checksum"],
            "retries": run.retries if run else 0,
            "error": run.error if run else None,
        }
        result["evidence_ids"] = [_register(session, ctx, "ingestion_status", result)]
        session.commit()
        return result


def window_metrics(ctx):
    with SessionLocal() as session, localcontext() as decimal_context:
        decimal_context.prec = 100
        snap = _snapshot(session, ctx)
        rows = _rows(session, ctx)
        midpoint = ctx.start + (ctx.end - ctx.start) / 2
        if ctx.source == "cex":
            values = [(utc(iso(r.open_time)), r.base_volume) for r in rows]
            key = "base_volume"
            unit = "ETH"
        else:
            values = [
                (
                    utc(iso(r.event_time)),
                    abs(Decimal(r.amount0))
                    / (Decimal(10) ** r.token_metadata["token0"]["decimals"]),
                )
                for r in rows
            ]
            key = "token0_volume"
            unit = "USDC"
        baseline = sum((v for t, v in values if t < midpoint), Decimal(0))
        current = sum((v for t, v in values if t >= midpoint), Decimal(0))
        coverage = _coverage(session, ctx, snap)
        compare_status = (
            "insufficient_samples"
            if (ctx.end - ctx.start).total_seconds() < 120 or not coverage["complete"]
            else "zero_baseline"
            if baseline == 0
            else "available"
        )
        if ctx.source == "cex" and (midpoint.second or midpoint.microsecond):
            compare_status = "insufficient_samples"
        change = (current - baseline) / baseline * 100 if compare_status == "available" else None
        result = {
            **_context(ctx),
            "row_count": len(rows),
            key: str(baseline + current),
            "volume_unit": unit,
            "number_of_trades": sum(r.number_of_trades for r in rows)
            if ctx.source == "cex" and rows and all(r.number_of_trades is not None for r in rows)
            else None,
            "coverage": coverage,
            "comparison": {
                "baseline_start": iso(ctx.start),
                "baseline_end": iso(midpoint),
                "current_start": iso(midpoint),
                "current_end": iso(ctx.end),
                "baseline_volume": str(baseline),
                "current_volume": str(current),
                "change_pct": str(change) if change is not None else None,
                "status": compare_status,
            },
        }
        if ctx.source == "cex":
            result["quote_volume"] = str(sum((r.quote_volume for r in rows), Decimal(0)))
            result["quote_unit"] = "USDT"
            result["close_price"] = str(rows[-1].close) if rows else None
        result["evidence_ids"] = [_register(session, ctx, "window_metrics", result)]
        session.commit()
        return result


def quality_findings(ctx):
    import os

    metrics = window_metrics(ctx)
    with SessionLocal() as session:
        snap = _snapshot(session, ctx)
        cov = _coverage(session, ctx, snap)
        lag = _lag(session, ctx, snap)
        quarantines = _quarantine_scope(session, ctx, snap)
        conflicts = _observations(session, ctx, "record_conflict")
        findings = []

        def add(rule, severity, expected, actual):
            item = {
                "rule": rule,
                "severity": severity,
                "expected": expected,
                "actual": actual,
                "detection_version": "quality-v2",
            }
            eid = _register(session, ctx, "quality_finding", item)
            item["evidence_ids"] = [eid]
            fid = "f-" + digest({**_context(ctx), **item})[:32]
            item["id"] = fid
            if session.get(QualityFinding, fid) is None:
                session.add(
                    QualityFinding(
                        id=fid, snapshot_id=ctx.snapshot_id, payload={**_context(ctx), **item}
                    )
                )
            findings.append(item)

        if not cov["window_covered"]:
            add(
                "window_outside_snapshot",
                "warning",
                "query contained in pinned manifest",
                {"snapshot_start": snap.manifest["start"], "snapshot_end": snap.manifest["end"]},
            )
        if cov["missing"]:
            add(
                "missing_candles" if ctx.source == "cex" else "unscanned_blocks",
                "error",
                {"missing": 0},
                {"missing": cov["missing"], "items": cov["missing_items"]},
            )
        if lag is not None and lag > 0 and cov["window_covered"]:
            add(
                "stale_data",
                "error",
                {"lag_seconds": 0},
                {"lag_seconds": lag, "reference": "pinned expected_end / query end"},
            )
        if quarantines["in_window"]:
            add(
                "invalid_rows",
                "error",
                {"quarantined_rows": 0},
                {
                    "quarantined_rows": len(quarantines["in_window"]),
                    "records": quarantines["in_window"][:10],
                },
            )
        if quarantines["unknown_time"]:
            add(
                "unlocated_invalid_rows",
                "warning",
                "bad rows have an attributable event time",
                {
                    "unknown_time_rows": len(quarantines["unknown_time"]),
                    "records": quarantines["unknown_time"][:10],
                    "limitation": "Cannot attribute these snapshot rows to or exclude them from the query window.",
                },
            )
        if not cov["coverage_known"] and cov["window_covered"]:
            add(
                "unknown_block_time_coverage",
                "warning",
                "pinned blocks anchor the full query interval",
                {"coverage_known": False, "lag_seconds": None},
            )
        if conflicts:
            add(
                "conflicting_records",
                "error",
                {"record_conflicts": 0},
                {"record_conflicts": len(conflicts), "records": conflicts[:10]},
            )
        comparison = metrics["comparison"]
        threshold = Decimal(os.getenv("VOLUME_DROP_THRESHOLD_PCT", "50"))
        if (
            comparison["status"] == "available"
            and comparison["change_pct"] is not None
            and Decimal(comparison["change_pct"]) <= -threshold
        ):
            add(
                "volume_change_pending_investigation",
                "info",
                {"drop_threshold_pct": str(threshold)},
                {
                    "change_pct": comparison["change_pct"],
                    "baseline_volume": comparison["baseline_volume"],
                    "current_volume": comparison["current_volume"],
                    "unit": metrics["volume_unit"],
                },
            )
        result = {
            **_context(ctx),
            "findings": findings,
            "has_data_issue": any(f["severity"] == "error" for f in findings),
            "has_unresolved_evidence": bool(quarantines["unknown_time"])
            or not cov["coverage_known"],
            "quarantine_scope": {k: len(v) for k, v in quarantines.items()},
            "checks": [
                "coverage",
                "freshness",
                "invalid_rows",
                "record_conflicts",
                "volume_change",
            ],
            "detection_version": "quality-v2",
        }
        result["evidence_ids"] = [_register(session, ctx, "quality_findings", result)] + [
            x for f in findings for x in f["evidence_ids"]
        ]
        session.commit()
        return result


def evidence(ids, snapshot_id):
    if len(ids) > 100:
        raise ValueError("at most 100 evidence ids")
    if not 1 <= len(snapshot_id) <= 80 or any(
        not isinstance(eid, str) or not 1 <= len(eid) <= 120 for eid in ids
    ):
        raise ValueError("invalid snapshot or evidence identifier length")
    with SessionLocal() as session:
        result = []
        for eid in ids:
            row = session.get(Evidence, eid)
            if row is None or row.snapshot_id != snapshot_id:
                raise ValueError("evidence not registered in bound snapshot")
            result.append({"id": row.id, "kind": row.kind, **row.payload})
        return result


def list_runs(limit=50):
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    with SessionLocal() as session:
        return [
            {
                "id": r.id,
                "snapshot_id": r.snapshot_id,
                "source": r.source,
                "status": r.status,
                "checkpoint": r.checkpoint,
                "retries": r.retries,
                "error": r.error,
                "created_at": iso(r.created_at),
            }
            for r in session.scalars(
                select(IngestionRun).order_by(IngestionRun.created_at.desc()).limit(limit)
            )
        ]


def chart(ctx):
    with SessionLocal() as session, localcontext() as decimal_context:
        decimal_context.prec = 100
        _snapshot(session, ctx)
        rows = _rows(session, ctx)[:1440]
        if ctx.source == "cex":
            return [
                {
                    "timestamp": iso(r.open_time),
                    "close": str(r.close),
                    "base_volume": str(r.base_volume),
                    "unit": "ETH",
                    "price_unit": "USDT",
                }
                for r in rows
            ]
        return [
            {
                "timestamp": iso(r.event_time),
                "token0_amount": str(
                    abs(Decimal(r.amount0)) / Decimal(10) ** r.token_metadata["token0"]["decimals"]
                ),
                "unit": "USDC",
            }
            for r in rows
        ]


def raw_samples(ctx):
    """Read only a registered batch; no caller-controlled paths or SQL."""
    with SessionLocal() as session:
        snap = _snapshot(session, ctx)
        batch = session.get(RawBatch, "raw-" + ctx.snapshot_id)
        if batch is None:
            return []
        allowed = (
            "provider",
            "symbol",
            "interval",
            "chain_id",
            "pool",
            "schema_version",
            "start",
            "end",
            "timestamp_unit",
            "synthetic",
            "checksum",
            "archive_checksum",
            "request_parameters",
            "token0",
            "token1",
            "metadata_verification",
        )
        manifest = {key: value for key, value in snap.manifest.items() if key in allowed}
        # Only expose registered relative locations inside this project. Never read a path here.
        raw_file = snap.manifest.get("raw_file", "")
        from pathlib import PurePosixPath

        path = PurePosixPath(raw_file.replace("\\", "/"))
        if not path.is_absolute() and ".." not in path.parts and ":" not in raw_file:
            manifest["raw_file"] = str(path)
        result = {
            **_context(ctx),
            "manifest": manifest,
            "batch_checksum": batch.checksum,
            "input_checksum": snap.manifest["input_checksum"],
            "raw_row_count": len(batch.payload["rows"]),
            "sample": batch.payload["rows"][:3],
            "sample_note": "First three rows from the pinned original raw batch; normalized fault versions may contain fewer rows.",
            "ingested_at": iso(batch.ingested_at),
        }
        result["evidence_ids"] = [_register(session, ctx, "raw_sample", result)]
        session.commit()
        return [result]
