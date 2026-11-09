import httpx
import pytest

from sentinel.collectors import RetryClient


@pytest.mark.parametrize("failure", [429, 500, "timeout"])
def test_retry_is_bounded_and_recovers(failure):
    calls = []
    delays = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("injected timeout", request=request)
            return httpx.Response(failure, headers={"Retry-After": "1"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    retry = RetryClient(
        httpx.Client(transport=httpx.MockTransport(handler)), retries=2, sleeper=delays.append
    )
    assert retry.request("GET", "https://example.test/data").json() == {"ok": True}
    assert len(calls) == 2 and retry.retry_count == 1 and len(delays) == 1


def test_retry_exhaustion_and_nonretryable_error():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, request=request)

    retry = RetryClient(
        httpx.Client(transport=httpx.MockTransport(handler)), retries=2, sleeper=lambda _: None
    )
    with pytest.raises(httpx.HTTPStatusError):
        retry.request("GET", "https://example.test/data")
    assert len(calls) == 3


def test_connected_dex_rejects_other_chain_and_range(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'collector.db'}")
    from sentinel.collectors import collect_dex

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": 1, "result": "0x89"}, request=request
        )

    retry = RetryClient(
        httpx.Client(transport=httpx.MockTransport(handler)), sleeper=lambda _: None
    )
    with pytest.raises(ValueError, match="mainnet chain ID"):
        collect_dex("https://rpc.example.test", client=retry)
    assert len(calls) == 1
    with pytest.raises(ValueError, match="pins blocks"):
        collect_dex("https://rpc.example.test", 1, 2, client=retry)


def test_failed_collection_logged_without_url_or_secret(tmp_path, monkeypatch):
    from sentinel.collectors import collect_dex
    from sentinel.service import list_runs

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'failed.db'}")

    def handler(request):
        return httpx.Response(403, request=request)

    client = RetryClient(
        httpx.Client(transport=httpx.MockTransport(handler)), sleeper=lambda _: None
    )
    with pytest.raises(httpx.HTTPStatusError):
        collect_dex("https://rpc.example.test/SECRET_KEY", client=client)
    run = list_runs()[0]
    assert run["status"] == "failed" and run["snapshot_id"] is None
    assert run["error"] == "HTTPStatusError HTTP 403"
    assert "SECRET_KEY" not in str(run)
    assert run["checkpoint"]["request_parameters"]["fromBlock"] == 19000000


def test_dex_abi_decode_precision_and_scanned_zero_blocks(tmp_path, monkeypatch):
    import json
    from datetime import datetime, timezone

    from sentinel.collectors import POOL, SWAP_TOPIC, collect_dex
    from sentinel.service import Context, window_metrics

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'abi.db'}")
    start = 19000000
    epoch = int(datetime(2024, 1, 15, tzinfo=timezone.utc).timestamp())
    amount0 = 123456789012345678901
    amount1 = -98765432109876543210987

    def block(number):
        return {
            "number": hex(number),
            "hash": "0x" + f"{number:064x}",
            "timestamp": hex(epoch + (number - start) * 12),
        }

    def handler(request):
        body = json.loads(request.content)
        method = body["method"]
        params = body["params"]
        if method == "eth_chainId":
            result = "0x1"
        elif method == "eth_getBlockByNumber":
            result = block(start + 100 if params[0] == "finalized" else int(params[0], 16))
        elif method == "eth_call":
            call = params[0]
            selector = call["data"]
            if selector == "0x0dfe1681":
                result = "0x" + "0" * 24 + "a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
            elif selector == "0xd21220a7":
                result = "0x" + "0" * 24 + "c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
            else:
                value = (
                    3000
                    if selector == "0xddca3f43"
                    else 6
                    if call["to"].lower().endswith("6eb48")
                    else 18
                )
                result = "0x" + f"{value:064x}"
        elif method == "eth_getLogs":
            result = []
            if int(params[0]["fromBlock"], 16) == start:
                encoded = "".join(f"{v % (2**256):064x}" for v in (amount0, amount1, 1, 1, 0))
                result = [
                    {
                        "address": POOL,
                        "topics": [SWAP_TOPIC, "0x" + "0" * 64, "0x" + "0" * 64],
                        "data": "0x" + encoded,
                        "blockNumber": hex(start),
                        "blockHash": block(start)["hash"],
                        "transactionHash": "0x" + "a" * 64,
                        "logIndex": "0x0",
                        "removed": False,
                    }
                ]
        else:
            raise AssertionError(method)
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": body["id"], "result": result}, request=request
        )

    client = RetryClient(
        httpx.Client(transport=httpx.MockTransport(handler)), sleeper=lambda _: None
    )
    item = collect_dex("https://rpc.example.test", client=client)
    context = Context(**{k: item[k] for k in ("source", "snapshot_id", "start", "end")})
    metrics = window_metrics(context)
    assert metrics["token0_volume"] == "123456789012345.678901"
    assert metrics["row_count"] == 1
    assert metrics["coverage"]["expected"] == 20 and metrics["coverage"]["complete"]
    assert metrics["number_of_trades"] is None
