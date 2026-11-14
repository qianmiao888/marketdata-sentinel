import argparse
import json

import pytest
from filelock import FileLock

from sentinel import db
from sentinel.cli import worker


def test_worker_checks_and_logs_without_overlap(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/worker.db")
    db.init_db()
    args = argparse.Namespace(interval=60, source="replay", day=None, once=True)
    with FileLock(str(tmp_path / "data" / "collector.lock"), timeout=0):
        with pytest.raises(ValueError, match="Another local worker"):
            worker(args)
    worker(args)
    events = [json.loads(x) for x in (tmp_path / "data" / "worker.jsonl").read_text().splitlines()]
    assert len(events) == 1 and events[0]["status"] == "success"
    assert len(events[0]["checks"]) == 2
    assert all(x["lag_seconds"] == 0 and "quality" in x for x in events[0]["checks"])


def test_demo_output_option_preserves_existing_artifact(tmp_path, monkeypatch, capsys):
    from sentinel.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'demo.db'}")
    previous = tmp_path / "data/demo-result.json"
    previous.parent.mkdir()
    previous.write_text("historical evidence", encoding="utf8")
    output = tmp_path / "new/demo.json"
    monkeypatch.setattr("sys.argv", ["sentinel", "demo", "--output", str(output)])
    main()
    artifact = json.loads(output.read_text())
    assert artifact["before"]["report"]["diagnosis"] == "observed_data_issue"
    assert artifact["after"]["report"]["diagnosis"] == "no_issue_found_in_checks"
    assert previous.read_text() == "historical evidence"
