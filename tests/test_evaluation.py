import copy
import json

import pytest

from sentinel.evaluation import (
    EVALS,
    QUESTION,
    load_cases,
    prepare_case,
    score_report,
    summarize,
    synthetic_input,
    verify_freeze,
)


def test_frozen_inputs_and_source_date_groups_do_not_overlap():
    verify_freeze()
    development = load_cases("development")
    acceptance = load_cases("acceptance")
    assert len(development) == len(acceptance) == 8
    assert {(c["source"], c["date"]) for c in development}.isdisjoint(
        {(c["source"], c["date"]) for c in acceptance}
    )
    assert {c["source"] for c in development}.isdisjoint({c["source"] for c in acceptance})


def test_freeze_detects_modification(tmp_path):
    for name in ("cases.json", "rubric.md", "freeze.json"):
        (tmp_path / name).write_bytes((EVALS / name).read_bytes())
    (tmp_path / "cases.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen input changed"):
        verify_freeze(tmp_path)


def test_oracle_and_recipe_not_in_registered_synthetic_inputs():
    case = load_cases("development")[1]
    rows, manifest = synthetic_input(case)
    encoded = json.dumps({"rows": rows, "manifest": manifest})
    assert case["expected"] not in encoded
    assert "recipe" not in manifest and "expected" not in manifest
    assert manifest["synthetic"] is True
    assert len(rows) == 20  # mutation is applied by the pipeline after pinning raw inputs


def test_failed_cases_stay_in_denominators():
    rows = [
        {
            "category": "fault",
            "score": {
                "success": False,
                **{
                    k: {"numerator": 0, "denominator": 1}
                    for k in ("diagnosis", "numeric", "evidence", "unknown_handling")
                },
            },
        }
    ]
    result = summarize(rows)
    assert result["all"]["success"] == {"numerator": 0, "denominator": 1}
    assert result["fault"]["diagnosis"]["denominator"] == 1


def test_grader_rejects_changed_number_and_unsupported_claim(tmp_path, monkeypatch):
    from sentinel import investigation, service

    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "grading.db"))
    case = load_cases("development")[0]
    ctx = prepare_case(case)
    truth = {
        "metrics": service.window_metrics(ctx),
        "status": service.ingestion_status(ctx),
        "quality": service.quality_findings(ctx),
    }
    result = investigation.investigate(ctx, QUESTION, baseline="A", persist=False)
    assert score_report(case, result, ctx, truth)["success"]
    wrong_number = copy.deepcopy(result)
    wrong_number["report"]["metrics"][0]["value"] = "999999"
    score = score_report(case, wrong_number, ctx, truth)
    assert score["numeric"]["numerator"] < score["numeric"]["denominator"]
    unsupported = copy.deepcopy(result)
    unsupported["report"]["facts"][0]["statement"] += " This proves an economic cause."
    score = score_report(case, unsupported, ctx, truth)
    assert score["evidence"]["numerator"] < score["evidence"]["denominator"]
