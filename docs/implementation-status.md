> 2026-11-13 更新：当前可运行工作台与本轮证据见[作品入口](workbench/index.md)。以下保留历史实施记录，各测试数字属于各自记录日期。

# Implementation and verification status

Current repair scope: **rule diagnosis + model evidence organization**. See [correctness-v2.md](correctness-v2.md) for four corrected behaviors, red-before-green logs, current78 offline/21 PostgreSQL passes, and separated system/model accounting. Original delivery records remain historical; current logs are [verification/correctness-v2/final/results.json](verification/correctness-v2/final/results.json).

Delivery date: 2026-11-01 (Asia/Shanghai). Specification: parent `MarketDataSentinel_Codex开发提示词.md`, read in full; parent research files preserved. This table distinguishes implemented code from exercised external integrations. Raw output/environment is in [verification/results.json](verification/results.json) and adjacent logs. No remote repository push, deployment or remote CI execution occurred.

| Milestone / requirement | Implementation | Actual verification | Status / boundary |
|---|---|---|---|
| M1 raw → normalized → results | `sentinel/models.py`, `pipeline.py`, `service.py` | fixed sample seed, HTTP metrics, offline tests | VERIFIED |
| PostgreSQL / migrations / precision | `alembic/versions/0001_initial.py`, `0002_failed_collection_runs.py`, `db.py` | PostgreSQL 17.2, Alembic head, four isolated-schema integration tests | VERIFIED on real PostgreSQL, separately from SQLite |
| Binance public sample | `fixtures/cex*`, `collectors.py` | official ZIP SHA-256 checked; 60-minute slice distributed; full 1,440-row external test | VERIFIED public data; upstream distribution terms linked |
| Source timestamp ms/us contract | `pipeline.parse_candle` | 2024 milliseconds / 2025 microseconds boundary and wrong-unit tests | VERIFIED; source date contract, not digit guessing |
| Decimal / raw signed amounts | exact numeric SQL type + raw integer strings | SQLite text exactness, PostgreSQL NUMERIC(78,30), int256 min/max + overflow quarantine | VERIFIED within supported schema precision |
| Idempotency / transaction checkpoint | scoped unique keys, content hashes, atomic normalized writes/checkpoint | repeat imports unchanged, interrupted rollback and resume on both backends | VERIFIED; bounded archive/range is re-fetched on network restart |
| Invalid rows / failed preflight | quarantine + nullable-snapshot failed ingestion runs | malformed rows visible; safe HTTP failure audit test | VERIFIED; no silent drops |
| API + validation | `sentinel/api.py`, `service.Context` | TestClient + actual localhost HTTP; injection-like strings, UTC/window bounds, cross-snapshot IDs | VERIFIED; no arbitrary SQL/path/shell input |
| M2 DEX fixed pool and ABI | `collectors.py`, `fixtures/dex_manifest.json` | mocked full RPC chain/finality/token/fee/decimals/log/hash contract; synthetic replay | VERIFIED adapter/offline only |
| Real DEX connection | explicit `ETH_RPC_URL`, fixed 19000000–19000019 inclusive | public provider chainId returned 0x1, subsequent collector request HTTP403 | BLOCKED; do not claim real swaps ingested |
| Scanned zero versus missing | `coverage` per block, quality rules | twenty scanned blocks with zero swaps valid; removed scan coverage detected | VERIFIED; synthetic/mocked cases |
| Freshness | replay pinned expected_end; historical requested connected scope plus publication allowance | normal historical replay lag0; stale tails fail; variable block timestamps | VERIFIED for requested historical scope, not a current-market feed |
| Quantity semantics / change rules | separate CEX ETH/USDT and DEX token0 USDC | source trades distinct from candle count, zero baseline, insufficient/incomplete/unequal-minute comparisons | VERIFIED; no price source / no DEX USD volume |
| Single periodic worker | CLI `worker`, filelock, JSONL | one-shot checks + lag logged; overlapping local lock rejected | VERIFIED local one-shot/lock; no multi-day observation or distributed lease |
| Isolated faults / recovery / reset | CLI `scenario`, `restore`, `reset`, `demo` | normal preserved;57/60 →60/60, report data versions pinned; scoped reset tests | VERIFIED from registered original raw; old faulty version stays available |
| Streamlit three tabs | `sentinel/ui.py` | real browser source/version selectors, overview, missing investigation, evidence and raw sample controls | VERIFIED visible UI; screenshots are actual captures |
| M2 demonstration readiness | migration → seed → normal/missing/stale → API/UI → recovery | first data-engineering demo recorded before AI final acceptance; clean PostgreSQL db `sentinel_clean` later repeated | VERIFIED key-free historical demonstration |
| M3 true model transport | `sentinel/llm.py` | HTTP mock contract tests for documented Chat Completions function protocol | VERIFIED protocol contract; actual model NOT RUN |
| Server-bound four read-only tools | `investigation.BoundTools` | malicious SQL/command/extra fields/source/window/snapshot/ID/budget tests | VERIFIED; tools only query registered data |
| Structured numeric/evidence report | canonical fact/metric catalog + content verification | exact metric, context and evidence tampering rejected; report persisted/retrieved in PostgreSQL | VERIFIED; model cannot add unconstrained verified prose |
| Bounds / failure / usage / cost | max4 calls/6 tools/45s deadline, output cap, fallback | timeout, tool/model/format/budget failures, missing usage/price unknown | VERIFIED via deterministic and test transports; no real-model billing |
| A/B/C initial-information fairness | same initial status/quality/metrics, C optional extra tools | runner and contract tests | A EXECUTED; B/C live NOT RUN, no claim of C advantage |
| M4 evaluation rubric/freeze | `evals/{rubric.md,cases.json,freeze.json}`, `.gitattributes` | byte-hash guard, split isolation, oracle non-leak tests; unchanged16-case suite | VERIFIED self-authored suite; target40 not met |
| Generated result table | `sentinel/evaluation.py`, `evals/results/correctness-v2` | A16/16 system reports,133/133 numbers,161/161 supported facts,2/2 unknown handling on SQLite/PostgreSQL | VERIFIED mechanical replay; live models NOT RUN; human semantics PENDING |
| Dependency lock / CI / containers | `pyproject.toml`, `uv.lock`, Dockerfile, compose, CI | frozen install succeeded; lint/format pass; equivalent local CI commands run | Docker and remote CI NOT RUN |
| English / Chinese handoff / resume / feedback | README and `docs/` | reviewed against implemented interfaces and actual logs | Delivered; no invented users/feedback/business results |

## Actual local launch and demonstrations

The final clean-state run created a new project-only PostgreSQL database `sentinel_clean`; no prior database was dropped. `scripts/start.ps1 -SkipInstall` migrated to head, imported both fixtures and created missing/stale isolated versions. Actual `/health`, `/ready`, `/snapshots`, `/metrics` and investigation/evidence routes responded successfully. CLI `demo` and `uv run --offline ... demo` completed with prepared dependencies. Main API/UI bind only `127.0.0.1` ports8000/8501.

The CEX recovery result was measured: **57 candles, 3 missing minutes, 6,933.4403 ETH** before; **60 candles, no missing minutes, 8,894.4444 ETH** after original raw replay. Reports changed from `observed_data_issue` to `no_issue_found_in_checks`; this does not establish absolute correctness or a market cause. Normal fixture trades are **54,290**, not60. Normal synthetic DEX has **7 swaps /20 scanned blocks /70 USDC single-side token0 quantity**.

Run artifacts under ignored `data/` include `demo-result.json`, `worker.jsonl`, service logs and process IDs. Durable test output is under `docs/verification`; generated evaluation reports are under `evals/results`. The comparison percentage was suppressed after actual UI inspection revealed it was being displayed for incomplete coverage; the earlier evaluation artifact and correction history are retained in `docs/evaluation.md`.

## Remaining external conditions and limits

1. A legally accessible Ethereum RPC supporting the fixed historical calls/logs is needed to verify real DEX ingestion. The public endpoint tested here returned403 after a successful chain ID read; no restriction bypass was attempted.
2. A configured accessible model provider/base URL/model/key is needed for genuine B/C runs. Live model performance, latency, tokens, fees and relative benefit remain unknown. Mock adapter tests never count as real model evaluation.
3. Docker installation/service is needed to exercise Compose. Current-machine testing used real portable PostgreSQL and native Python processes.
4. The benchmark has16 cases instead of40; expanding requires independent source/date/fault groups and a newly frozen version. Existing acceptance is known to the developers; it is a regression suite, not an external benchmark.
5. Human semantic audit and real-person trial feedback are pending. No tester, customer or feedback is fabricated.
6. No seven-day operation, full live chain reorganization support, warehouse-scale aggregation, multiworker coordination, real-time SLA or public deployment has been demonstrated. The local worker was observed for actual one-shot execution only.

The nonblocking Starlette TestClient/httpx deprecation warning is retained in test output; it does not turn a skipped or unexecuted check into a pass.
