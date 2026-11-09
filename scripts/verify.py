"""Capture actual checks and their unedited output; no prefilled pass counts."""

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--postgres", action="store_true")
parser.add_argument("--external-cex", action="store_true")
parser.add_argument(
    "--output-dir", type=Path, help="Store this run separately from previous verification artifacts"
)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = args.output_dir or root / "docs" / "verification"
out.mkdir(parents=True, exist_ok=True)
commands = [
    ("lint", [sys.executable, "-m", "ruff", "check", "."], True),
    ("format", [sys.executable, "-m", "ruff", "format", "--check", "."], True),
    (
        "offline",
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "not postgres and not external and not live_llm",
            "-q",
        ],
        True,
    ),
    (
        "postgres",
        [sys.executable, "-m", "pytest", "-m", "postgres", "-q"],
        args.postgres and bool(os.getenv("TEST_POSTGRES_URL")),
    ),
    (
        "external-cex",
        [sys.executable, "-m", "pytest", "tests/test_external.py", "-k", "binance", "-q"],
        args.external_cex,
    ),
]
record = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "platform": platform.platform(),
    "python": sys.version,
    "cpu": platform.processor(),
    "dependencies": {
        n: importlib.metadata.version(n)
        for n in ("fastapi", "streamlit", "sqlalchemy", "alembic", "psycopg", "pytest", "ruff")
    },
    "checks": [],
    "live_llm": "NOT RUN: use the separately opt-in live evaluation runner",
    "docker_compose": "NOT RUN: this script does not exercise Docker Compose",
}
failed = False
for name, command, enabled in commands:
    if not enabled:
        record["checks"].append({"name": name, "status": "NOT RUN", "command": command[2:]})
        continue
    env = dict(os.environ)
    if name == "external-cex":
        env["RUN_EXTERNAL_SMOKE"] = "1"
    start = datetime.now(timezone.utc)
    result = subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf8",
        errors="replace",
        timeout=180,
    )
    content = result.stdout + result.stderr
    (out / f"{name}.txt").write_text(content, encoding="utf8")
    record["checks"].append(
        {
            "name": name,
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "exit_code": result.returncode,
            "started_at": start.isoformat(),
            "elapsed_seconds": (datetime.now(timezone.utc) - start).total_seconds(),
            "command": command[2:],
            "log": f"{name}.txt",
        }
    )
    failed |= result.returncode != 0
    print(name, record["checks"][-1]["status"])
(out / "results.json").write_text(json.dumps(record, indent=2), encoding="utf8")
sys.exit(int(failed))
