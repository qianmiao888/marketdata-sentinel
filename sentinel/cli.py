"""Explicit local data operations; investigation tools never call these writes."""

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from filelock import FileLock, Timeout

load_dotenv()


def output(value):
    print(json.dumps(value, indent=2, default=str))


def worker(args):
    from sentinel import collectors, pipeline, service

    if args.interval < 60:
        raise ValueError(
            "Minimum schedule interval is 60 seconds; archives are not a real-time feed"
        )
    lock_dir = Path("data")
    lock_dir.mkdir(exist_ok=True)
    try:
        with FileLock(str(lock_dir / "collector.lock"), timeout=0):
            while True:
                started = datetime.now(timezone.utc)
                try:
                    if args.source == "replay":
                        result = pipeline.seed()
                    else:
                        # Daily archives are published after the day ends. Leave an extra day.
                        day = (
                            args.day
                            or (datetime.now(timezone.utc).date() - timedelta(days=2)).isoformat()
                        )
                        result = collectors.collect_cex(day)
                    items = result.get("snapshots", [result])
                    checks = []
                    for item in items:
                        scope = service.Context(
                            **{k: item[k] for k in ("source", "snapshot_id", "start", "end")}
                        )
                        status = service.ingestion_status(scope)
                        checks.append(
                            {
                                "snapshot_id": item["snapshot_id"],
                                "lag_seconds": status["lag_seconds"],
                                "quality": service.quality_findings(scope),
                            }
                        )
                    event = {
                        "worker_started": started.isoformat(),
                        "status": "success",
                        "result": result,
                        "checks": checks,
                    }
                except Exception as exc:
                    event = {
                        "worker_started": started.isoformat(),
                        "status": "failed",
                        "error": type(exc).__name__,
                    }
                with (lock_dir / "worker.jsonl").open("a", encoding="utf8") as handle:
                    handle.write(json.dumps(event, default=str) + "\n")
                output(event)
                if args.once:
                    return
                time.sleep(args.interval)
    except Timeout:
        raise ValueError("Another local worker holds this task lock")


def main():
    parser = argparse.ArgumentParser(description="MarketData Sentinel local operations")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Import fixed snapshots; safe to repeat")
    scenario = sub.add_parser("scenario", help="Create an isolated immutable fault version")
    scenario.add_argument("kind", choices=["normal", "missing", "stale"])
    for command in ("restore", "reset"):
        child = sub.add_parser(command)
        child.add_argument("snapshot_id")
    sub.add_parser("snapshots")
    demo = sub.add_parser("demo", help="Seed -> missing -> investigate -> restore -> compare")
    demo.add_argument("--output", type=Path, default=Path("data/demo-result.json"))
    for command in ("check", "investigate"):
        child = sub.add_parser(command)
        child.add_argument("snapshot_id")
        child.add_argument(
            "--question", default="Check whether the volume change is supported by complete data."
        )
        child.add_argument("--mode", choices=["deterministic", "live_llm"], default="deterministic")
        child.add_argument("--baseline", choices=["A", "B", "C"], default="A")
    collect = sub.add_parser("collect-cex")
    collect.add_argument("day", help="UTC archive date YYYY-MM-DD")
    dex = sub.add_parser("collect-dex")
    dex.add_argument("--start-block", type=int, required=True)
    dex.add_argument(
        "--end-block", type=int, required=True, help="Inclusive fixed block bound (19000019)"
    )
    schedule = sub.add_parser("worker")
    schedule.add_argument("--source", choices=["replay", "cex"], default="replay")
    schedule.add_argument("--once", action="store_true")
    schedule.add_argument("--interval", type=int, default=86400)
    schedule.add_argument("--day")
    args = parser.parse_args()
    from sentinel import collectors, pipeline, service

    def ctx(sid):
        item = next((s for s in service.list_snapshots() if s["snapshot_id"] == sid), None)
        if item is None:
            raise ValueError("Unknown snapshot")
        return service.Context(
            source=item["source"], snapshot_id=sid, start=item["start"], end=item["end"]
        )

    try:
        if args.command == "seed":
            output(pipeline.seed())
        elif args.command == "scenario":
            output(pipeline.scenario(args.kind))
        elif args.command == "restore":
            output(pipeline.restore(args.snapshot_id))
        elif args.command == "reset":
            output(pipeline.reset(args.snapshot_id))
        elif args.command == "snapshots":
            output(service.list_snapshots())
        elif args.command == "collect-cex":
            output(collectors.collect_cex(args.day))
        elif args.command == "collect-dex":
            url = os.getenv("ETH_RPC_URL")
            if not url:
                raise ValueError("ETH_RPC_URL is required for connected collection")
            output(collectors.collect_dex(url, args.start_block, args.end_block))
        elif args.command == "worker":
            worker(args)
        elif args.command == "check":
            scope = ctx(args.snapshot_id)
            output(
                {
                    "metrics": service.window_metrics(scope),
                    "quality": service.quality_findings(scope),
                    "ingestion": service.ingestion_status(scope),
                }
            )
        elif args.command == "investigate":
            from sentinel.investigation import investigate

            output(
                investigate(
                    ctx(args.snapshot_id), args.question, mode=args.mode, baseline=args.baseline
                )
            )
        elif args.command == "demo":
            from sentinel.investigation import investigate

            normal = pipeline.seed()
            fault = pipeline.scenario("missing")
            snapshots = fault.get("snapshots", [fault])
            item = next(s for s in snapshots if s["source"] == "cex")
            before = investigate(
                ctx(item["snapshot_id"]), "Check coverage and volume before recovery.", baseline="A"
            )
            restored = pipeline.restore(item["snapshot_id"])
            # restore may return one snapshot or the standard snapshots wrapper.
            recovered = restored.get("snapshots", [restored])[0]
            after = investigate(
                ctx(recovered["snapshot_id"]),
                "Check coverage and volume after raw replay.",
                baseline="A",
            )
            artifact = {
                "normal": normal,
                "fault": fault,
                "before": before,
                "restored": restored,
                "after": after,
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf8")
            output(artifact)
    except httpx.HTTPStatusError as exc:
        parser.exit(
            2, f"Collection failed: HTTP {exc.response.status_code}. Credentials and URL omitted.\n"
        )
    except httpx.HTTPError:
        parser.exit(2, "Collection failed: transport error. Credentials and URL omitted.\n")
    except (ValueError, KeyError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
