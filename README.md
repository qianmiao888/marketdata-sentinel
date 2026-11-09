# MarketData Sentinel

A Python workbench for investigating market-data quality: **find a gap, inspect its evidence, and restore the data from registered raw inputs.**

Built with **Python · FastAPI · PostgreSQL · SQLAlchemy/Alembic · pytest · Streamlit**. The project demonstrates precise data ingestion, idempotent storage, failure recovery, bounded APIs, and reproducible testing.

[Quick start](#quick-start) · [Two-minute demo](docs/demo-script.md) · [Architecture and data dictionary](docs/architecture.md) · [Verification](docs/correctness-v2.md) · [中文快速上手](docs/quickstart-zh.md)

![Missing-minute markers in the historical CEX replay](docs/screenshots/missing-chart.jpg)

*Actual local UI capture from the initial implementation. The correctness-v2 repair is documented separately; this screenshot is historical, not a new capture or a live market feed.*

## What it does

When a chart shows lower volume, first establish whether its data is complete and valid. The workbench connects the observation to its source window, ingestion state, exact metrics, and raw evidence.

- **Collect and replay:** one Binance ETHUSDT archive source and one Ethereum Uniswap v3 pool adapter, with input manifests and checksums.
- **Store reliably:** exact decimal quantities, UTC `[start, end)` windows, idempotent imports, atomic row/checkpoint commits, and retained duplicate/conflict evidence.
- **Check quality:** missing intervals, stale tails, malformed rows, conflicting identities, and window-scoped uncertainty. Scanned blocks distinguish valid zero swaps from missing collection.
- **Investigate with evidence:** a FastAPI service and three-tab UI expose data versions, quality findings, bounded raw samples, and reports.
- **Recover reproducibly:** replay registered raw data into a content-addressed version while preserving earlier faulty versions and reports.

**AI scope: rule diagnosis + model evidence organization.** Rules/code determine the diagnosis and numerical facts. An optional model can organize validated facts and choose bounded read-only queries. The default demonstration requires no model key. Real-model evaluation is still pending.

## Demonstration: 57/60 → 60/60 candles

The included CEX sample is real public history. A deliberate fault removes three minutes from an isolated version; recovery replays the original raw inputs.

| Check | Missing version | Restored version |
| --- | --- | --- |
| Candles in the one-hour window | 57/60 | 60/60 |
| Missing minutes | 3 | 0 |
| ETH base volume | 6,933.4403 | 8,894.4444 |
| Rule diagnosis | `observed_data_issue` | `no_issue_found_in_checks` |

```bash
uv run python -m sentinel.cli demo
```

The command writes the before/after artifact to `data/demo-result.json`. Recovery preserves the faulty version for comparison; it does not edit an old report. Follow the [two-minute walkthrough](docs/demo-script.md) to reproduce the UI investigation and inspect [actual report evidence](docs/screenshots/report-evidence.jpg).

The distributed DEX replay is **synthetic**: seven swaps across twenty explicitly scanned blocks. It is useful for testing coverage and units, and is not evidence of real chain ingestion.

## Architecture

```mermaid
flowchart LR
    A[Public CEX archive / fixed DEX input] --> B[Collect and validate]
    B --> C[Raw manifest and checksum]
    B --> D[(PostgreSQL)]
    D --> E[Quality checks and exact metrics]
    E --> F[FastAPI]
    F --> G[Streamlit workbench]
    E --> H[Rule diagnosis]
    H --> I[Evidence report]
    H --> J[Optional bounded model adapter]
    J --> I
    C --> K[Deterministic recovery]
    K --> D
```

The convenience local replay can use SQLite; PostgreSQL is exercised separately by integration tests. Queries are parameterized, evidence is bound to a source/window/version, and the model has no arbitrary SQL, shell, or database-write tool. Detailed schemas and tradeoffs are in the [architecture](docs/architecture.md) and [engineering notes](docs/engineering-notes.md).

## Quick start

Requirements: **Python 3.12 and uv**. The first dependency installation needs network access. After dependencies are cached, the fixed replay runs offline without API keys.

```bash
git clone https://github.com/qianmiao888/marketdata-sentinel.git
cd marketdata-sentinel
uv sync --all-extras --frozen
```

On Windows PowerShell, start the API and UI:

```powershell
.\scripts\start.ps1 -SkipInstall
```

The script migrates the database, loads the two fixed sources, prepares missing/stale scenarios, and starts local services. Open the **local** [workbench](http://127.0.0.1:8501) and [API documentation](http://127.0.0.1:8000/docs). Stop processes started by the script with `scripts/stop.ps1`.

Without `DATABASE_URL`, the local demo uses SQLite with exact decimal text storage. To use an existing PostgreSQL database, set its connection string **before** starting the services:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/sentinel'
.\scripts\start.ps1 -SkipInstall
```

Optional settings are documented in [`.env.example`](.env.example). Stop existing project services before changing database settings: the startup script reuses responding local services. Logs and process IDs are in ignored `data/`.

For Linux/macOS or manual startup, run these commands from the project directory; keep the same database environment in both terminals:

```bash
uv run alembic upgrade head
uv run python -m sentinel.cli seed
uv run python -m sentinel.cli scenario missing
uv run python -m sentinel.cli scenario stale
uv run uvicorn sentinel.api:app --host 127.0.0.1 --port 8000
# In a second terminal:
uv run streamlit run sentinel/ui.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

**Docker Compose is provided but has not been executed in the recorded environment.** To try it with Docker available, use `docker compose up --build -d`. An optional archive worker uses `docker compose --profile worker up -d worker`. See [`compose.yaml`](compose.yaml); images need an initial network pull, and `docker compose down` preserves the database volume.

## Verified behavior

The recorded correctness-v2 run used Python 3.12 and PostgreSQL 17.2. These are **local results**, not a claimed remote CI run or production benchmark.

| Verification | Recorded result | Evidence |
| --- | --- | --- |
| Offline test suite | **78 passed** | [Logs and environment](docs/verification/correctness-v2/final/results.json) |
| Real PostgreSQL integration suite | **21 passed** | [PostgreSQL log](docs/verification/correctness-v2/final/postgres.txt) |
| Lint and formatting | Passed | [Verification results](docs/verification/correctness-v2/final/results.json) |
| Deterministic A baseline, SQLite and PostgreSQL | **16/16** system reports; **133/133** numeric references; **161/161** evidence-supported facts | [SQLite output](evals/results/correctness-v2/A-all-sqlite-final.md) / [PostgreSQL output](evals/results/correctness-v2/A-all-postgres-final.md) |
| Public Binance archive collection | One full day, **1,440 candles** | [Earlier verification](docs/verification/results.json) |

The sixteen-case self-authored synthetic suite is a regression benchmark. A has no model score. For B/C, a correct template fallback can count toward system report correctness but never toward model completion or correctness; failures remain in the model denominator. [Correctness-v2](docs/correctness-v2.md) explains the four fixes, regression evidence, metric definitions, and preserved historical outputs.

Run the checks:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -m 'not postgres and not external and not live_llm' -q
$env:TEST_POSTGRES_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/sentinel_test'
uv run pytest -m postgres -q
uv run python -m sentinel.evaluation --split all --baseline A
```

PostgreSQL tests create and clean up their own random schemas. External collection and real-model evaluation are explicit opt-ins. The repository includes a [GitHub Actions workflow](.github/workflows/ci.yml) for lint, formatting, offline tests, and PostgreSQL tests; the linked local logs remain distinct from any subsequent Actions results.

## Connected data and optional models

Fixed replay and actual connected collection are labeled separately. CEX collection reads daily archives rather than a real-time feed:

```powershell
uv run python -m sentinel.cli collect-cex 2025-01-01
uv run python -m sentinel.cli worker --source replay --once
# Poll daily CEX archives with one local worker:
uv run python -m sentinel.cli worker --source cex --interval 86400
```

The DEX adapter targets Ethereum chain 1 and the USDC/WETH 0.3% pool `0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8`, fixed historical blocks 19000000–19000019 inclusive. It validates chain/finality, token metadata, fee, block hashes, and Swap fields. Actual historical ingestion remains blocked after an earlier public RPC returned HTTP 403; replay and mocked adapter tests do not replace that verification. Source details are in [fixtures/README.md](fixtures/README.md).

For optional model calls, configure `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`. The adapter implements a configurable Chat Completions tool protocol. Calls, additional tools, output tokens, and elapsed time are bounded. Missing usage or configured pricing is reported as unknown. A model failure produces an explicitly labeled deterministic fallback.

```powershell
# Without --live, B/C write NOT RUN artifacts and make no model request:
uv run python -m sentinel.evaluation --split all --baseline B
uv run python -m sentinel.evaluation --split all --baseline C
# Real execution requires configured credentials and explicit opt-in:
uv run python -m sentinel.evaluation --split all --baseline C --live
```

See [evaluation design and limitations](docs/evaluation.md). Real B/C accuracy, latency, costs, and any benefit over templates have **not been measured**.

## Scope and next validation

- One ETHUSDT pair and one Ethereum pool; CEX and DEX quantities remain separate. Token0 USDC quantity is not labeled USD volume.
- Historical replay and bounded collection; no full live reorganization handling, multi-day SLA, or warehouse-scale performance claim.
- Real DEX ingestion, real-model B/C evaluation, Docker execution, and human semantic review remain pending.
- The application is a local demonstration with loopback-bound services and no authentication. No public deployment, users, or business savings are claimed.

## Project guide

| Path | Purpose |
| --- | --- |
| [`sentinel/`](sentinel/) | Collectors, storage, quality/metrics, API, investigation, UI, and CLI |
| [`alembic/`](alembic/) | Database migrations |
| [`tests/`](tests/) | Offline, PostgreSQL, collector, API, and model-contract tests |
| [`fixtures/`](fixtures/) | Small reproducible samples and source manifests |
| [`evals/`](evals/) | Frozen cases, rubric, and recorded results |
| [`docs/`](docs/) | Architecture, demonstration, verification, and engineering decisions |

Additional documentation: [implementation status](docs/implementation-status.md), [中文快速上手](docs/quickstart-zh.md), [engineering notes](docs/engineering-notes.md), [resume evidence](docs/resume-bullets.md), and [MIT license](LICENSE).

<details>
<summary>Original development-machine PostgreSQL notes</summary>

The original Windows environment used an ignored portable PostgreSQL installation under `.local/`, listening only on `127.0.0.1:55432`. These binaries and databases are not distributed with the repository; new machines should supply their own PostgreSQL or use the SQLite replay. The historical environment is described in the [implementation record](docs/implementation-status.md).

On that original machine only, if its server is stopped, run from the project directory:

```powershell
& '.local\postgres\pgsql\bin\pg_ctl.exe' -D '.local\pgdata' -l '.local\postgres.log' -o '-h 127.0.0.1 -p 55432' start
```

Then set `DATABASE_URL` as described in the [Chinese quick start](docs/quickstart-zh.md). Its loopback trust authentication was for a disposable development instance.

</details>
