> 2026-11-13 更新：当前可运行工作台与本轮证据见[作品入口](docs/workbench/index.md)。以下保留历史实施记录，各测试数字属于各自记录日期。

# MarketData Sentinel implementation plan

Specification: ../MarketDataSentinel_Codex开发提示词.md (read in full 2026-11-01).
Existing research in parent directory is preserved. No existing project or applicable AGENTS.md found.

## Milestones and acceptance
- [x] M1: raw manifests, real CEX fixture/collector, migrations, exact metrics API/CLI. Four real PostgreSQL integration tests passed; offline timestamp/idempotency/recovery checks passed.
- [x] M2 local replay: single-pool synthetic DEX, scanned-block coverage, quality, three-tab UI, missing/stale versions and raw restoration. Actual UI exercised and screenshots saved. Real DEX collection remains BLOCKED by HTTP403.
- [x] M3 implemented and contract-tested: bounded tools, validated/persisted reports, configurable real HTTP tool-call adapter, explicit fallback, A/B/C runner. Live B/C model evaluations NOT RUN without model/provider/key.
- [x] M4 local delivery: frozen16-case evaluation (8 development/8 acceptance), clean PostgreSQL launch, actual browser interactions, documentation and evidence-based resume. Target40 cases, human semantic review, Docker execution and genuine live LLM/DEX verification remain explicitly incomplete.

## Verification commands (to be finalized with CLI)
- uv sync --all-extras --frozen
- uv run ruff check . && uv run ruff format --check .
- uv run pytest -m "not postgres and not external and not live_llm"
- DATABASE_URL=... uv run pytest -m postgres
- uv run alembic upgrade head
- uv run python -m sentinel.cli seed / demo / restore / check
- uv run python -m sentinel.evaluation --split all --baseline A
- uv run uvicorn sentinel.api:app --host 127.0.0.1 --port 8000
- uv run streamlit run sentinel/ui.py --server.address 127.0.0.1

## Environment and decisions
- Windows PowerShell, Python 3.12.9, uv 0.6.8, Git and Node available.
- Docker, PostgreSQL CLI/server not on PATH; no C:\Program Files\PostgreSQL detected. Investigate portable PostgreSQL; otherwise explicitly BLOCKED.
- No model/RPC/database variables detected (only names checked; secrets never printed).
- Default local demo may use SQLite as an explicitly identified convenience backend; PostgreSQL integration is a separate mandatory result, never inferred from SQLite.
- Synthetic fixtures remain explicitly synthetic unless public retrieval and provenance are verified.
- Only local development and necessary public reads; no deployment, remote push, or purchasing.

## Progress / handoff
2026-11-01: specification/background/environment read; implementation starting. Actual results will be recorded after execution.

## Final local acceptance — 2026-11-01

- Installed59 locked packages on Python3.12.9/Windows11. PostgreSQL17.2 portable binaries prepared under ignored `.local/`; server bound only127.0.0.1:55432. Docker still unavailable.
- Created a fresh project-only `sentinel_clean` database without deleting previous data. `scripts/start.ps1 -SkipInstall` ran Alembic0001→0002, seed, missing/stale scenarios and hidden API/UI. `/ready` and UI health returned200. Native PostgreSQL integration is distinct from the SQLite evaluation backend.
- Final captured checks: **56 offline tests passed;4 PostgreSQL tests passed;1 external Binance daily archive smoke passed; lint and format passed.** Exact environment/times/logs: `docs/verification/results.json`. One nonblocking Starlette/httpx deprecation warning retained.
- Actual data demo: normal CEX60 rows/54,290 trades/8,894.4444 ETH; missing57 rows/3 gaps/6,933.4403 ETH; deterministic raw replay returns normal version with coverage60/60. CLI demo also executed with uv offline mode after dependency preparation.
- Actual browser: normal/missing selectors, UTC chart/red gap markers, investigation facts, report evidence, raw manifest/sample, old-report suppression after scope change, recovery report, model-unavailable labeled fallback, DEX synthetic marker and block coverage. Captures: `docs/screenshots/`; UI fallback text retained under verification.
- Latest frozen A evaluation: diagnosis16/16, numbers134/134, supported facts162/162, insufficient handling2/2. Earlier139/139 and167/167 artifact retained before correcting unsupported incomplete-window comparisons; cases/rubric unchanged and no prompts tuned from acceptance. B/C real models NOT RUN; human semantic review PENDING.
- Public Ethereum chainId returned0x1, subsequent connected collector HTTP403; sanitized failure retained in PostgreSQL and `docs/verification/external-dex.json`. No access restriction bypass attempted. Distributed DEX remains synthetic.
- Fixed real development defects: timestamp boundary/precision, canonical hashes, nullable failed preflight runs, omitted-check model fallback, evidence-content mismatch, signed int256 minimum, stale UI report cache, browser timezone rendering, incomplete/unequal-minute percentage comparisons. Tests and engineering notes explain them.

## Remaining conditions / follow-up

1. Accessible authorized Ethereum historical RPC for the fixed range and a provider/base URL/model/key for live B/C evaluation. Do not overwrite NOT RUN/BLOCKED labels until actual execution.
2. Docker service to exercise provided Compose; remote CI has not been run or pushed.
3. Expand independent cases in a new freeze rather than duplicating the current16 to claim40. Record real human semantic audit and trial feedback using the delivered template.
4. No production deployment, multi-day uptime, distributed worker lease, unrestricted AI reasoning or live reorganization support is claimed. Resume bullets use only implemented/measured facts.

The project is locally runnable and reviewable. Parent research files remain untouched. Start/stop commands, full modes/limitations and exact replay steps are in README and docs. Services may remain running on8000/8501 with their own recorded PIDs; portable PostgreSQL remains on55432.

## Correctness repair v2 — 2026-11-01

Scope: rules diagnose; the model organizes evidence. No product expansion.

- [x] Add regressions first for fallback/model accounting, identical vs conflicting records, window-scoped quarantine, DEX empty inter-block windows. Before fixes:11 failed/9 PostgreSQL variants deselected; raw log `docs/verification/correctness-v2/red.txt`.
- [x] Record hashes of previous evaluation files; do not overwrite them.
- [x] Implement and verify accounting with B/C failures retained in model denominators. System report / model completion / all-attempt model correctness / conditional completed-model correctness are separate; fallback and test adapters never count as live completion. Existing output paths are rejected before cases run.
- [x] Preserve full duplicate/conflict raw/value evidence and both row references, including malformed non-key values. Retain first valid normalized row; replay does not inflate counts. Scope quarantine as in-window/outside/unknown, preserving original totals and raw data.
- [x] Use block interval overlap for DEX coverage and lag, including predecessor blocks, irregular spacing and trailing intervals. No anchor means unknown freshness, not a fabricated zero or proof of completeness.
- [x] Execute complete offline and real PostgreSQL suites:78 offline/21 PostgreSQL passed, lint/format passed. New regressions account for39 backend variants. Logs in `docs/verification/correctness-v2/final` preserve original verification logs.
- [x] New unchanged-v1-suite evaluations on SQLite and PostgreSQL: system reports16/16, numbers133/133, evidence161/161, unknown2/2. Final files in `evals/results/correctness-v2/*-final.json`; genuine B/C remain NOT RUN. Original outputs and frozen files preserved; checksums independently checked.

Correctness-v2 requires no schema change; new JSON metadata/evidence works with migration0002. Pre-v2 quarantines are time-classified from original rows on read. Existing snapshots with previously suppressed conflicts require raw replay to populate observation evidence; old reports stay historical. Product scope is explicitly rules diagnosing + models organizing evidence. README, architecture/evaluation/status/engineering/Chinese quickstart/resume docs updated; `docs/correctness-v2.md` contains exact definitions, reproductions and limits. Native API/UI restarted against existing `sentinel_clean` without deleting its data; service smoke checks recorded separately.
