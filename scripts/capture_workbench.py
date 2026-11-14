"""Capture real local HTTP workflow and portable deliverables without model calls."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from sentinel.pipeline import digest, utc

parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", type=Path, required=True)
parser.add_argument("--api", default="http://127.0.0.1:8000")
args = parser.parse_args()
out = args.output_dir
out.mkdir(parents=True, exist_ok=True)
if (out / "summary.json").exists():
    raise SystemExit("Choose a fresh output directory; existing capture will not be overwritten")
commands = []
with httpx.Client(base_url=args.api, timeout=90, trust_env=False) as client:

    def call(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        commands.append(
            {"method": method, "path": path, "status_code": response.status_code, **kwargs}
        )
        response.raise_for_status()
        return response.json()

    ready = call("GET", "/ready")
    snapshots = call("GET", "/snapshots", params={"limit": 200})
    item = next(
        s
        for s in snapshots
        if s["source"] == "cex"
        and s["transform"] == "missing"
        and s["start"].startswith("2025-01-01T00:00")
    )
    scope = {k: item[k] for k in ("source", "snapshot_id", "start", "end")}
    before = call(
        "POST",
        "/investigations",
        json={
            "context": scope,
            "question": "这张行情图的成交数量能否作为完整时间窗口的数字引用？请检查完整性并提供依据。",
            "mode": "deterministic",
            "baseline": "A",
        },
    )
    receipt = call("POST", "/recoveries", json={"before_run_id": before["run_id"]})
    bundle = call(
        "GET",
        f"/investigations/{before['run_id']}/communication",
        params={"recovery_id": receipt["id"]},
    )
    after = call("GET", f"/investigations/{receipt['after_run_id']}")
    raw = call("GET", "/raw-samples", params=scope)
    old = call("GET", f"/investigations/{before['run_id']}")
    assert old == before, "Old report changed during recovery"
    assert receipt["restore_status"] == "completed"
    assert before["report"]["source"] == after["report"]["source"]
    assert before["report"]["window"] == after["report"]["window"]

    # Validate the actual HTTP export, including nested comparison evidence.
    groups = [("evidence", bundle["report"], bundle["evidence"])] + [
        (f"comparison.versions[{index}].evidence", version["report"], version["evidence"])
        for index, version in enumerate(bundle["comparison"]["versions"])
    ]
    hash_checks = []
    fact_checks = []
    business_metrics = {
        "row_count",
        "base_volume",
        "quote_volume",
        "token0_volume",
        "coverage_expected",
        "coverage_observed",
        "coverage_missing",
    }
    for location, report, entries in groups:
        registered = call(
            "GET",
            "/evidence",
            params=[("snapshot_id", report["snapshot_id"])]
            + [("ids", entry["id"]) for entry in entries],
        )
        assert entries == registered, f"Export differs from registered evidence: {location}"
        for index, entry in enumerate(entries):
            assert entry["id"].startswith("e-")
            payload = {key: value for key, value in entry.items() if key not in {"id", "kind"}}
            recomputed = "e-" + digest({"kind": entry["kind"], "payload": payload})[:32]
            hash_checks.append(
                {
                    "location": f"{location}[{index}]",
                    "id": entry["id"],
                    "recomputed_id": recomputed,
                    "matches": entry["id"] == recomputed,
                }
            )
            assert entry["id"] == recomputed, f"Export hash mismatch: {location}"
        assert report["source"] == bundle["context"]["source"]
        for bound in ("start", "end"):
            assert utc(report["window"][bound]) == utc(bundle["context"][bound])
        for text_key in ("markdown_zh", "markdown_en", "issue_markdown"):
            text = bundle[text_key]
            assert report["snapshot_id"] in text
            assert f"UTC [{bundle['context']['start']}, {bundle['context']['end']})" in text
            for metric in report["metrics"]:
                if metric["name"] not in business_metrics:
                    continue
                exact_cells = (
                    f"| {metric['value']} | {metric['unit']} | "
                    f"{', '.join(metric['evidence_ids'])} |"
                )
                assert exact_cells in text, (
                    f"Metric/unit/reference mismatch: {location}, {text_key}"
                )
                fact_checks.append(
                    {
                        "location": location,
                        "document": text_key,
                        "snapshot_id": report["snapshot_id"],
                        "metric": metric["name"],
                        "value": metric["value"],
                        "unit": metric["unit"],
                        "matches": True,
                    }
                )
    assert bundle["metrics"] == bundle["report"]["metrics"]

(out / "export-checks.json").write_text(
    json.dumps(
        {
            "algorithm": "e- + pipeline.digest({kind, payload})[:32]; only id/kind transport fields excluded",
            "registered_payloads_unchanged": True,
            "hash_checks": hash_checks,
            "fact_checks": fact_checks,
            "source_window_and_versions_consistent": True,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf8",
)

for name, value in (
    ("before-report", before),
    ("after-report", after),
    ("recovery", receipt),
    ("evidence", bundle),
    ("raw-samples", raw),
):
    (out / f"{name}.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8"
    )
(out / "communication-zh.md").write_text(bundle["markdown_zh"], encoding="utf8")
(out / "communication-en.md").write_text(bundle["markdown_en"], encoding="utf8")
(out / "issue.md").write_text(bundle["issue_markdown"], encoding="utf8")
summary = {
    "captured_at_utc": datetime.now(UTC).isoformat(),
    "api": args.api,
    "ready": ready,
    "context": scope,
    "before_run_id": before["run_id"],
    "after_run_id": after["run_id"],
    "recovery_id": receipt["id"],
    "old_report_preserved": old == before,
    "versions": [
        {
            "role": role,
            "snapshot_id": report["snapshot_id"],
            "diagnosis": report["diagnosis"],
            "metrics": {
                m["name"]: {"value": m["value"], "unit": m["unit"]} for m in report["metrics"]
            },
        }
        for role, report in (("before", before["report"]), ("after", after["report"]))
    ],
    "human_usability": "PENDING: no real participants tested",
    "commands": commands,
}
(out / "summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8"
)
print(
    json.dumps(
        {"status": "captured", "before_run_id": before["run_id"], "after_run_id": after["run_id"]}
    )
)
