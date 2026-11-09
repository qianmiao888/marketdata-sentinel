from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import zipfile
from datetime import date, datetime, timedelta, timezone

import httpx

from sentinel.pipeline import ROOT, import_snapshot

POOL = "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"
SWAP_TOPIC = "0xc42079f94a6350d7e6235f291749249f928cc2ac818eb64fed8004e115fbcca67"


class RetryClient:
    def __init__(self, client=None, retries=3, sleeper=time.sleep):
        self.client = client or httpx.Client(timeout=httpx.Timeout(20.0), follow_redirects=False)
        self.retries = retries
        self.retry_count = 0
        self.sleeper = sleeper

    def request(self, method, url, **kwargs):
        for attempt in range(self.retries + 1):
            try:
                response = self.client.request(method, url, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == self.retries:
                        response.raise_for_status()
                    retry = response.headers.get("Retry-After", "")
                    delay = (
                        min(float(retry), 30)
                        if retry.replace(".", "", 1).isdigit()
                        else min(2**attempt, 8)
                    )
                    self.retry_count += 1
                    self.sleeper(delay)
                    continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == self.retries:
                    raise
                self.retry_count += 1
                self.sleeper(min(2**attempt, 8))
        raise RuntimeError("retry budget exhausted")


def _collect_cex(day, client=None):
    selected = date.fromisoformat(day)
    if selected >= datetime.now(timezone.utc).date():
        raise ValueError("daily archive must be a completed UTC day")
    start = datetime.combine(selected, datetime.min.time(), tzinfo=timezone.utc)
    url = f"https://data.binance.vision/data/spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-{selected.isoformat()}.zip"
    client = client or RetryClient()
    content = client.request("GET", url).content
    if len(content) > 10_000_000:
        raise ValueError("archive exceeds 10 MB bound")
    checksum = client.request("GET", url + ".CHECKSUM").text.split()[0]
    if hashlib.sha256(content).hexdigest() != checksum:
        raise ValueError("archive checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        if len(names) != 1 or archive.getinfo(names[0]).file_size > 20_000_000:
            raise ValueError("unexpected archive structure")
        raw = archive.read(names[0])
    rows = list(csv.reader(raw.decode().splitlines()))
    directory = ROOT / "data" / "raw"
    directory.mkdir(parents=True, exist_ok=True)
    raw_path = directory / f"ETHUSDT-1m-{selected.isoformat()}-{checksum[:12]}.csv"
    raw_path.write_bytes(raw)
    manifest = {
        "source": "cex",
        "provider": "binance",
        "symbol": "ETHUSDT",
        "interval": "1m",
        "schema_version": "binance-spot-kline-v1",
        "start": start.isoformat(),
        "end": (start + timedelta(days=1)).isoformat(),
        "expected_end": (start + timedelta(days=1)).isoformat(),
        "timestamp_unit": "us" if selected >= date(2025, 1, 1) else "ms",
        "synthetic": False,
        "mode": "connected collection",
        "publication_delay_seconds": 86400,
        "raw_file": str(raw_path.relative_to(ROOT)),
        "checksum": hashlib.sha256(raw).hexdigest(),
        "archive_checksum": checksum,
        "request_parameters": {"date": day, "url": url},
        "collection_retries": client.retry_count,
    }
    result = import_snapshot("cex", rows, manifest)
    _record_retries(result["snapshot_id"], client.retry_count)
    return result


def _record_retries(sid, count):
    from sqlalchemy import select

    from sentinel.db import SessionLocal
    from sentinel.models import IngestionRun

    with SessionLocal() as session:
        run = session.scalars(
            select(IngestionRun)
            .where(IngestionRun.snapshot_id == sid)
            .order_by(IngestionRun.created_at.desc())
        ).first()
        if run:
            run.retries = count
            session.commit()


def _collect_dex(rpc_url, start_block=19000000, end_block=19000019, client=None):
    if (start_block, end_block) != (19000000, 19000019):
        raise ValueError("v1 connected collector pins blocks 19000000..19000019 inclusive")
    if not rpc_url.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):
        raise ValueError("RPC requires HTTPS or local node")
    client = client or RetryClient()
    rpc_id = 0

    def rpc(method, params):
        nonlocal rpc_id
        rpc_id += 1
        payload = client.request(
            "POST",
            rpc_url,
            json={"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params},
        ).json()
        if payload.get("error") or "result" not in payload:
            raise ValueError("RPC returned error or absent result")
        return payload["result"]

    if int(rpc("eth_chainId", []), 16) != 1:
        raise ValueError("expected Ethereum mainnet chain ID 1")
    finalized = rpc("eth_getBlockByNumber", ["finalized", False])
    if int(finalized["number"], 16) < end_block:
        raise ValueError("range is not finalized")
    manifest = json.loads((ROOT / "fixtures/dex_manifest.json").read_text(encoding="utf-8-sig"))
    tag = hex(end_block)

    def call(address, selector):
        return rpc("eth_call", [{"to": address, "data": selector}, tag])

    # Selectors token0(), token1(), decimals(), fee(). Pool ABI is the canonical Uniswap v3 interface.
    token0 = "0x" + call(POOL, "0x0dfe1681")[-40:]
    token1 = "0x" + call(POOL, "0xd21220a7")[-40:]
    if (
        token0.lower() != manifest["token0"]["address"]
        or token1.lower() != manifest["token1"]["address"]
    ):
        raise ValueError("pool token metadata mismatch")
    if (
        int(call(token0, "0x313ce567"), 16) != 6
        or int(call(token1, "0x313ce567"), 16) != 18
        or int(call(POOL, "0xddca3f43"), 16) != 3000
    ):
        raise ValueError("decimals/fee mismatch")
    blocks = []
    rows = []
    for number in range(start_block, end_block + 1):
        b = rpc("eth_getBlockByNumber", [hex(number), False])
        blocks.append(
            {
                "number": number,
                "hash": b["hash"],
                "timestamp": datetime.fromtimestamp(
                    int(b["timestamp"], 16), timezone.utc
                ).isoformat(),
            }
        )
    by_number = {b["number"]: b for b in blocks}
    for first in range(start_block, end_block + 1, 5):
        last = min(first + 4, end_block)
        logs = rpc(
            "eth_getLogs",
            [
                {
                    "address": POOL,
                    "fromBlock": hex(first),
                    "toBlock": hex(last),
                    "topics": [SWAP_TOPIC],
                }
            ],
        )
        if len(logs) > 10000:
            raise ValueError("log response exceeds bound")
        for log in logs:
            if (
                log.get("removed")
                or log.get("address", "").lower() != POOL
                or not log.get("topics")
                or log["topics"][0].lower() != SWAP_TOPIC
            ):
                raise ValueError("unexpected or removed log")
            encoded = log["data"].removeprefix("0x")
            if len(encoded) != 64 * 5:
                raise ValueError("invalid Swap ABI data length")
            amount0 = int(encoded[:64], 16)
            amount1 = int(encoded[64:128], 16)
            amount0 = amount0 - 2**256 if amount0 >= 2**255 else amount0
            amount1 = amount1 - 2**256 if amount1 >= 2**255 else amount1
            number = int(log["blockNumber"], 16)
            if number not in by_number or not first <= number <= last:
                raise ValueError("log outside requested segment")
            rows.append(
                {
                    "chain_id": 1,
                    "pool": POOL,
                    "block_number": number,
                    "block_hash": log["blockHash"],
                    "tx_hash": log["transactionHash"],
                    "log_index": int(log["logIndex"], 16),
                    "event_time": by_number[number]["timestamp"],
                    "amount0": str(amount0),
                    "amount1": str(amount1),
                }
            )
    # Re-read all pinned hashes: an inconsistent provider response is rejected before commit.
    for b in blocks:
        if rpc("eth_getBlockByNumber", [hex(b["number"]), False])["hash"] != b["hash"]:
            raise ValueError("block hash changed during collection")
    start = datetime.fromisoformat(blocks[0]["timestamp"])
    following = rpc("eth_getBlockByNumber", [hex(end_block + 1), False])
    end = datetime.fromtimestamp(int(following["timestamp"], 16), timezone.utc)
    manifest.update(
        {
            "blocks": blocks,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "expected_end": end.isoformat(),
            "synthetic": False,
            "mode": "connected collection",
            "publication_delay_seconds": 0,
            "metadata_verification": "eth_chainId / finalized / eth_call token0 token1 decimals fee / block hashes checked",
            "request_parameters": {"fromBlock": start_block, "toBlock": end_block},
            "collection_retries": client.retry_count,
        }
    )
    directory = ROOT / "data" / "raw"
    directory.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(rows, sort_keys=True).encode()
    checksum = hashlib.sha256(raw).hexdigest()
    path = directory / f"dex-{start_block}-{end_block}-{checksum[:12]}.json"
    path.write_bytes(raw)
    manifest["raw_file"] = str(path.relative_to(ROOT))
    manifest["checksum"] = checksum
    result = import_snapshot("dex", rows, manifest)
    _record_retries(result["snapshot_id"], client.retry_count)
    return result


def _collection_failure(source, parameters, error, retries=0):
    from uuid import uuid4

    from sentinel.db import SessionLocal, init_db
    from sentinel.models import IngestionRun

    init_db()
    # URLs may contain API keys: persist only error type/status, never exception URL/body.
    status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
    safe_error = type(error).__name__ + (f" HTTP {status}" if status else "")
    with SessionLocal() as session:
        session.add(
            IngestionRun(
                id="run-" + uuid4().hex,
                snapshot_id=None,
                source=source,
                status="failed",
                checkpoint={"request_parameters": parameters, "processed": 0},
                retries=retries,
                error=safe_error,
            )
        )
        session.commit()


def collect_cex(day, client=None):
    client = client or RetryClient()
    try:
        return _collect_cex(day, client=client)
    except Exception as error:
        _collection_failure(
            "cex", {"date": day, "symbol": "ETHUSDT", "interval": "1m"}, error, client.retry_count
        )
        raise


def collect_dex(rpc_url, start_block=19000000, end_block=19000019, client=None):
    client = client or RetryClient()
    try:
        return _collect_dex(rpc_url, start_block, end_block, client=client)
    except Exception as error:
        _collection_failure(
            "dex",
            {"chain_id": 1, "pool": POOL, "fromBlock": start_block, "toBlock": end_block},
            error,
            client.retry_count,
        )
        raise
