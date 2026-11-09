from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select

from sentinel.db import SessionLocal, init_db
from sentinel.models import (
    Candle,
    Coverage,
    Evidence,
    IngestionRun,
    InvestigationRun,
    QualityFinding,
    Quarantine,
    RawBatch,
    Snapshot,
    Swap,
)

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def utc(value):
    result = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if result.tzinfo is None:
        raise ValueError("UTC timezone required")
    return result.astimezone(UTC)


def iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def decimal(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("non-finite numeric value")
    # NUMERIC(78,30): reject instead of silently rounding beyond storage precision.
    if result and (result.as_tuple().exponent < -30 or result.adjusted() >= 48):
        raise ValueError("numeric value exceeds NUMERIC(78,30) precision")
    return result


def parse_candle(row, manifest):
    if len(row) != 12:
        raise ValueError("expected 12 Binance spot kline fields")
    start = utc(manifest["start"])
    unit = manifest["timestamp_unit"]
    expected_unit = "us" if start.date().isoformat() >= "2025-01-01" else "ms"
    if unit != expected_unit:
        raise ValueError("timestamp unit violates Binance spot date contract")
    ticks = int(row[0])
    divisor = 1_000_000 if unit == "us" else 1000
    t = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
        microseconds=ticks if unit == "us" else ticks * 1000
    )
    if not start <= t < utc(manifest["end"]) or t.second or t.microsecond:
        raise ValueError("timestamp outside manifest or not minute aligned")
    close_time = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
        microseconds=int(row[6]) if divisor == 1_000_000 else int(row[6]) * 1000
    )
    if not t <= close_time < t + timedelta(minutes=1):
        raise ValueError("invalid close timestamp unit/range")
    values = [decimal(row[i]) for i in (1, 2, 3, 4, 5, 7)]
    o, h, low, c, b, q = values
    if min(values) < 0 or min(o, h, low, c) <= 0 or h < max(o, c) or low > min(o, c) or low > h:
        raise ValueError("invalid OHLC or negative volume")
    trades = int(row[8])
    if trades < 0:
        raise ValueError("negative number_of_trades")
    return dict(
        open_time=t,
        open=o,
        high=h,
        low=low,
        close=c,
        base_volume=b,
        quote_volume=q,
        number_of_trades=trades,
    )


def _parse_swap(row, manifest, blocks):
    if (
        manifest.get("chain_id") != 1
        or manifest.get("pool", "").lower() != "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"
        or manifest.get("token0", {}).get("address", "").lower()
        != "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
        or manifest.get("token1", {}).get("address", "").lower()
        != "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    ):
        raise ValueError("manifest is not the configured Ethereum USDC/WETH pool")
    b = int(row["block_number"])
    if b not in blocks or row["block_hash"].lower() != blocks[b]["hash"].lower():
        raise ValueError("swap block hash is not canonical in pinned manifest")
    if int(row["chain_id"]) != 1 or row["pool"].lower() != manifest["pool"].lower():
        raise ValueError("pool/chain mismatch")
    if manifest["token0"]["decimals"] != 6 or manifest["token1"]["decimals"] != 18:
        raise ValueError("token decimals disagree with configured pool")
    amounts = [str(int(row[k])) for k in ("amount0", "amount1")]
    if any(not -(2**255) <= int(x) < 2**255 for x in amounts):
        raise ValueError("amount outside signed int256")
    if int(amounts[0]) * int(amounts[1]) >= 0:
        raise ValueError("Swap amounts must have opposite signs")
    t = utc(row["event_time"])
    if t != utc(blocks[b]["timestamp"]) or not utc(manifest["start"]) <= t < utc(manifest["end"]):
        raise ValueError("swap event time differs from block/window")
    for key in ("block_hash", "tx_hash"):
        if len(row[key]) != 66 or not row[key].startswith("0x"):
            raise ValueError("invalid hash")
        int(row[key][2:], 16)
    return dict(
        chain_id=1,
        pool=manifest["pool"].lower(),
        block_number=b,
        block_hash=row["block_hash"].lower(),
        tx_hash=row["tx_hash"].lower(),
        log_index=int(row["log_index"]),
        event_time=t,
        amount0=amounts[0],
        amount1=amounts[1],
        token_metadata={"token0": manifest["token0"], "token1": manifest["token1"]},
    )


def row_event_time(source, row, manifest):
    """Recover time independently of value validation, without guessing units.

    A registered block number scopes the rejected row, even when its hash is
    invalid; this does not certify that row as a canonical event.
    Also used when reading pre-v2 quarantines, so old raw evidence is preserved.
    """
    try:
        if source == "cex":
            expected = "us" if utc(manifest["start"]).date().isoformat() >= "2025-01-01" else "ms"
            if manifest.get("timestamp_unit") != expected:
                return None, "unresolved"
            ticks = int(row[0])
            event = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
                microseconds=ticks if expected == "us" else ticks * 1000
            )
            if event.second or event.microsecond:
                return None, "unresolved"
            return iso(event), "cex_open_time"
        number = int(row["block_number"])
        block = next(b for b in manifest["blocks"] if b["number"] == number)
        basis = (
            "canonical_block"
            if isinstance(row.get("block_hash"), str)
            and row["block_hash"].lower() == block["hash"].lower()
            else "registered_block_reference"
        )
        return iso(utc(block["timestamp"])), basis
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, StopIteration):
        return None, "unresolved"


def _canonical(value):
    """Compare normalized values exactly across SQLite/PostgreSQL scale formatting."""
    if isinstance(value, datetime):
        return iso(value)
    if isinstance(value, Decimal):
        if value == 0:
            return "0"
        fixed = format(value, "f")
        return fixed.rstrip("0").rstrip(".") if "." in fixed else fixed
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    return value


def record_identity(source, row, manifest):
    """Recover only the natural key, even when a non-key value is malformed."""
    try:
        if source == "cex":
            return row_event_time(source, row, manifest)[0]
        if int(row["chain_id"]) != 1 or row["pool"].lower() != manifest["pool"].lower():
            return None
        hashes = [row[k].lower() for k in ("block_hash", "tx_hash")]
        for h in hashes:
            if len(h) != 66 or not h.startswith("0x"):
                return None
            int(h[2:], 16)
        index = int(row["log_index"])
        return (*hashes, index) if index >= 0 else None
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def _observe_duplicate(
    session, sid, batch_id, position, row_index, accepted_index, key, old, new, event_time
):
    kind = "record_duplicate" if old == new else "record_conflict"
    eid = "o-" + digest({"snapshot": sid, "position": position, "kind": kind})[:32]
    if session.get(Evidence, eid) is None:
        session.add(
            Evidence(
                id=eid,
                snapshot_id=sid,
                kind=kind,
                payload={
                    "snapshot_id": sid,
                    "raw_batch_id": batch_id,
                    "row_index": row_index,
                    "accepted_row_index": accepted_index,
                    "natural_key": key,
                    "event_time": event_time,
                    "accepted": old,
                    "incoming": new,
                    "record_type": kind,
                    "retained_policy": "First valid normalized row is retained. The earlier raw reference may itself be quarantined; inspect validation_status.",
                },
            )
        )


def import_snapshot(source, rows, manifest, *, fault=None, interrupt_after=None):
    """Pin inputs; resume commits rows and checkpoint together. Faults create isolated versions."""
    init_db()
    manifest = dict(manifest)
    if source not in ("cex", "dex"):
        raise ValueError("unsupported source")
    if utc(manifest["end"]) <= utc(manifest["start"]):
        raise ValueError("invalid manifest window")
    original_rows = rows
    original_blocks = manifest.get("blocks", [])
    selected = list(enumerate(rows))
    blocks = list(original_blocks)
    if fault == "missing":
        if source == "cex":
            middle = len(selected) // 2
            selected = [x for x in selected if x[0] not in range(middle, middle + 3)]
        else:
            middle = len(blocks) // 2
            removed = {b["number"] for b in blocks[middle : middle + 3]}
            blocks = [b for b in blocks if b["number"] not in removed]
            selected = [x for x in selected if x[1]["block_number"] not in removed]
    elif fault == "stale":
        if source == "cex":
            selected = selected[:-5]
        else:
            removed = {b["number"] for b in blocks[-5:]}
            blocks = blocks[:-5]
            selected = [x for x in selected if x[1]["block_number"] not in removed]
    elif fault == "invalid" and selected:
        index, first = selected[0]
        first = list(first) if source == "cex" else dict(first)
        first[5 if source == "cex" else "amount0"] = "bad-number"
        selected[0] = (index, first)
    elif fault == "duplicate":
        selected += selected[:1]
    elif fault == "out_of_order":
        selected.reverse()
    elif fault not in (None, "normal"):
        raise ValueError("unsupported fault")
    payload = {"rows": original_rows, "manifest": manifest}
    checksum = digest(payload)
    sid = "s-" + digest({"source": source, "payload": checksum, "transform": fault})[:24]
    batch_id = "raw-" + sid
    # The fault label stays in raw lineage, never in read-only tool responses.
    pinned = {
        **manifest,
        "source": source,
        "input_checksum": checksum,
        "transform": fault,
        "mode": manifest.get("mode", "snapshot replay"),
    }
    with SessionLocal() as session:
        snap = session.get(Snapshot, sid)
        if snap is None:
            session.add(Snapshot(id=sid, source=source, manifest=pinned))
            session.flush()
            session.add(
                RawBatch(
                    id=batch_id,
                    snapshot_id=sid,
                    checksum=checksum,
                    manifest=pinned,
                    payload=payload,
                )
            )
            session.commit()
        else:
            batch = session.get(RawBatch, batch_id)
            if batch.checksum != checksum:
                raise ValueError("immutable snapshot checksum conflict")
        run = IngestionRun(
            id="run-" + uuid4().hex,
            snapshot_id=sid,
            source=source,
            status="running",
            checkpoint={"processed": 0, "total": len(selected)},
            retries=0,
            error=None,
        )
        session.add(run)
        session.commit()
        run_id = run.id
    try:
        with SessionLocal() as session:
            run = session.get(IngestionRun, run_id)
            block_map = {b["number"]: b for b in original_blocks}
            model = Candle if source == "cex" else Swap
            fields = (
                (
                    "open_time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "base_volume",
                    "quote_volume",
                    "number_of_trades",
                )
                if source == "cex"
                else (
                    "chain_id",
                    "pool",
                    "block_number",
                    "block_hash",
                    "tx_hash",
                    "log_index",
                    "event_time",
                    "amount0",
                    "amount1",
                    "token_metadata",
                )
            )
            seen = {}
            for stored in session.scalars(select(model).where(model.snapshot_id == sid)):
                identity = (
                    iso(stored.open_time)
                    if source == "cex"
                    else (stored.block_hash, stored.tx_hash, stored.log_index)
                )
                seen[identity] = _canonical({k: getattr(stored, k) for k in fields})
            first_raw = {}
            for n, (index, row) in enumerate(selected):
                if interrupt_after is not None and n >= interrupt_after:
                    raise RuntimeError("injected interruption before transaction commit")
                identity = record_identity(source, row, manifest)
                event_time, time_basis = row_event_time(source, row, manifest)
                values = None
                stored_conflict = None
                try:
                    values = (
                        parse_candle(row, manifest)
                        if source == "cex"
                        else _parse_swap(row, manifest, block_map)
                    )
                    key = (
                        iso(values["open_time"])
                        if source == "cex"
                        else (values["block_hash"], values["tx_hash"], values["log_index"])
                    )
                    if key not in seen:
                        session.add(model(snapshot_id=sid, raw_batch_id=batch_id, **values))
                        seen[key] = _canonical(values)
                    elif key not in first_raw and seen[key] != _canonical(values):
                        stored_conflict = seen[key]
                except (
                    ValueError,
                    InvalidOperation,
                    KeyError,
                    TypeError,
                    OverflowError,
                    AttributeError,
                ) as e:
                    qid = f"q-{sid}-{index}"
                    if session.get(Quarantine, qid) is None:
                        session.add(
                            Quarantine(
                                id=qid,
                                snapshot_id=sid,
                                raw_batch_id=batch_id,
                                row_index=index,
                                reason=f"{type(e).__name__}: {e}",
                                raw={
                                    "row": row,
                                    "event_time": event_time,
                                    "time_basis": time_basis,
                                    "time_schema_version": "row-time-v2",
                                },
                            )
                        )
                if identity is not None:
                    incoming = {
                        **_canonical(values or {}),
                        "raw_fields": row,
                        "validation_status": "valid" if values is not None else "invalid",
                    }
                    if identity in first_raw:
                        old, first_index = first_raw[identity]
                        _observe_duplicate(
                            session,
                            sid,
                            batch_id,
                            n,
                            index,
                            first_index,
                            identity,
                            old,
                            incoming,
                            event_time,
                        )
                    elif stored_conflict is not None:
                        _observe_duplicate(
                            session,
                            sid,
                            batch_id,
                            n,
                            index,
                            None,
                            identity,
                            {**stored_conflict, "raw_fields": None, "validation_status": "stored"},
                            incoming,
                            event_time,
                        )
                    first_raw.setdefault(identity, (incoming, index))
                run.checkpoint = {"processed": n + 1, "total": len(selected)}
            if source == "dex":
                existing = {
                    x.block_number: x.block_hash
                    for x in session.scalars(select(Coverage).where(Coverage.snapshot_id == sid))
                }
                for block in blocks:
                    if block["number"] in existing and existing[block["number"]] != block["hash"]:
                        raise ValueError("canonical block hash changed")
                    if block["number"] not in existing:
                        session.add(
                            Coverage(
                                snapshot_id=sid,
                                block_number=block["number"],
                                block_hash=block["hash"],
                                event_time=utc(block["timestamp"]),
                            )
                        )
                run.checkpoint = {
                    **run.checkpoint,
                    "last_scanned_block": max((b["number"] for b in blocks), default=None),
                }
            session.flush()
            quarantined = session.scalar(
                select(Quarantine.id).where(Quarantine.snapshot_id == sid).limit(1)
            )
            conflict = session.scalar(
                select(Evidence.id)
                .where(Evidence.snapshot_id == sid, Evidence.kind == "record_conflict")
                .limit(1)
            )
            run.status = (
                "partial" if quarantined or conflict or fault in ("missing", "stale") else "success"
            )
            session.commit()
    except Exception as e:
        with SessionLocal() as session:
            run = session.get(IngestionRun, run_id)
            run.status = "failed"
            run.error = f"{type(e).__name__}: {e}"
            session.commit()
        raise
    return {
        "snapshot_id": sid,
        "source": source,
        "start": manifest["start"],
        "end": manifest["end"],
        "status": "imported",
    }


def seed():
    result = []
    for source in ("cex", "dex"):
        manifest = json.loads(
            (ROOT / f"fixtures/{source}_manifest.json").read_text(encoding="utf-8-sig")
        )
        raw = (ROOT / manifest["raw_file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["checksum"]:
            raise ValueError("fixture checksum mismatch")
        rows = list(csv.reader(raw.decode().splitlines())) if source == "cex" else json.loads(raw)
        result.append(import_snapshot(source, rows, manifest))
    return {"snapshots": result}


def scenario(kind):
    if kind not in ("normal", "missing", "stale", "invalid", "duplicate", "out_of_order"):
        raise ValueError("unsupported scenario")
    normal = seed()
    if kind == "normal":
        return normal
    result = []
    with SessionLocal() as session:
        batches = [session.get(RawBatch, "raw-" + x["snapshot_id"]) for x in normal["snapshots"]]
        payloads = [(b.manifest["source"], b.payload) for b in batches]
    for source, payload in payloads:
        result.append(import_snapshot(source, payload["rows"], payload["manifest"], fault=kind))
    return {"snapshots": result}


def restore(snapshot_id):
    with SessionLocal() as session:
        batch = session.get(RawBatch, "raw-" + snapshot_id)
        if batch is None:
            raise ValueError("snapshot not found")
        payload = batch.payload
        source = batch.manifest["source"]
    return import_snapshot(source, payload["rows"], payload["manifest"])


def reset(snapshot_id):
    with SessionLocal() as session:
        snap = session.get(Snapshot, snapshot_id)
        if snap is None:
            raise ValueError("snapshot not found")
        if not snap.manifest.get("transform"):
            raise ValueError("reset only accepts isolated fault snapshots")
        for model in (
            InvestigationRun,
            QualityFinding,
            Evidence,
            Quarantine,
            Coverage,
            Candle,
            Swap,
            IngestionRun,
            RawBatch,
        ):
            session.execute(delete(model).where(model.snapshot_id == snapshot_id))
        session.delete(snap)
        session.commit()
    return {"deleted_snapshot_id": snapshot_id}
