# Correctness repair v2 — 2026-11-01

Product scope: **rule diagnosis + model evidence organization**（规则诊断＋模型整理证据）. Rules/code establish the diagnosis and numerical facts; a configured model may select/order validated evidence and choose bounded read tools. This round adds no product features outside that scope.

## Regressions before fixes

`tests/test_correctness_v2.py` was introduced before changing the implementation. The initial offline run produced **11 failures** across all four requested areas; the unedited log is [red.txt](verification/correctness-v2/red.txt). Subsequent boundary regressions were also run failing before their fixes: absent block anchors, ambiguous report wording/output preservation, malformed-value key collisions, and a null DEX hash. Their red logs are retained beside it. Existing assertions were retained; no core tests were skipped to obtain a green run.

| Area | Reproduction in the regression file | Delivered behavior |
|---|---|---|
| Fallback versus model success | `test_fallback_report_success_is_not_live_model_success`, `test_runner_keeps_successful_fallbacks_in_model_failure_denominator` | System reports may succeed through deterministic fallback; live model completion/correctness never count that fallback as success. Failed model cases remain in all-attempt denominators. |
| Exact duplicate versus conflicting identity | `test_identical_duplicates_and_conflicting_values_are_distinct`, `test_conflicts_include_source_fields_not_present_in_normalized_schema`, `test_conflicting_key_is_retained_even_when_one_value_cannot_be_parsed` | Compare full raw fields and exact normalized values. Store a deterministic observation per duplicate/conflict occurrence; preserve both versions, key, batch, earlier/incoming row indexes and validation status. Keep the first valid normalized row, emit `conflicting_records` error evidence, and mark the ingestion partial. Replay does not inflate counts. |
| Window-scoped bad rows | `test_outside_bad_rows_do_not_contaminate_query_window`, `test_unknown_time_bad_rows_require_uncertainty_not_local_issue`, `test_quarantine_half_open_scope_and_known_issue_precedes_uncertainty` | `quarantined_rows` means known in-window rows. `quarantine_scope` independently reports `in_window`, `outside_window`, `unknown_time`; `quarantined_rows_total` preserves the snapshot total. Known outside rows do not create a local error. Unknown-time rows produce warning/evidence and an insufficient-evidence report unless a confirmed local issue already exists. |
| Empty DEX subwindows | `test_dex_empty_time_window_uses_overlapping_predecessor_block`, `test_dex_no_block_anchor_cannot_certify_an_empty_window` | Intersect the query with `[block_time, next_block_time)`, including a preceding block whose timestamp is outside the query. Complete scans give zero lag/valid zero events; removing that scan gives a coverage gap and lag. No block anchor means `coverage_known=false`, unknown lag and insufficient evidence. |

Malformed values with a recoverable identity remain both quarantined and conflict-traceable; a completely unidentifiable row remains quarantine evidence and is not assigned a guessed key. A DEX row with a known registered block number can be scoped from that block's timestamp even when its own hash/amount is invalid. `time_basis=registered_block_reference` explicitly distinguishes that reference from an accepted canonical event. The invalid identity is still rejected, never imported as a valid Swap.

## Accounting definitions

For each category and overall, the new scorer reports:

| Metric | Numerator | Denominator |
|---|---|---|
| `system_report_accuracy` | Reports satisfying diagnosis, numerical and evidence checks, **including successful template fallback** | All executed cases |
| `model_completion_rate` | B/C cases with requested/actual `live_llm`, completed validated output, no failure and at least one model call | All executed B/C cases, including timeout/tool/format/budget failures and fallback |
| `model_accuracy` | Completed live-model reports also satisfying the factual rubric | All executed B/C cases, including failures |
| `completed_model_accuracy` | Same completed-and-correct reports | Completed live-model cases only; explicitly conditional |

Legacy `diagnosis`, `numeric`, `evidence`, `unknown_handling` and `success` remain system-level mechanical measures for compatibility. They must not be relabeled as model performance. The conditional metric is not a replacement for the all-attempt accuracy. A has no model denominator (`0/0`, not applicable); unexecuted B/C has status `NOT RUN` with no measured scores, not fabricated failures or successes.

The accounting contract test supplies **fictional** records: one completed/correct model result, one completed/incorrect result, one correct fallback, one test-adapter result and one failed result. Expected counters are system3/5, live completion2/5, live correctness1/5 and conditional1/2. These numbers verify the counter contract; **they are not real model measurements**. The runner tests separately simulate eight successful fallbacks and assert system8/8 versus model0/8, with all eight listed as model failures. No external model request is made in these tests.

For B/C, an actual failed/incorrect model attempt now makes the CLI return a nonzero exit code even if all fallback system reports are correct. Missing configuration detected before cases begin creates a `NOT RUN` artifact; it is not an attempted-model failure.

## Actual verification and results

Final complete suites: **78 offline passed;21 real PostgreSQL passed**, including **39 new regression variants** (22 offline/17 PostgreSQL). Logs/environment/timestamps: [verification/correctness-v2/final/results.json](verification/correctness-v2/final/results.json). Ruff lint/format passed. A nonblocking Starlette/httpx TestClient deprecation warning remains visible. PostgreSQL17.2 tests own random schemas and clean up only their schemas. No new external CEX/RPC/model calls or Docker execution were required in this repair round.

New evaluation outputs are under `evals/results/correctness-v2/`; final code results use `A-all-sqlite-final.json` and `A-all-postgres-final.json`. The unchanged known16-case frozen replay suite yields on both backends:

- System diagnosis and full report correctness: **16/16**.
- Numeric references: **133/133**; evidence-supported facts: **161/161**.
- Insufficient-evidence handling: **2/2**.
- A model measures: not applicable; B/C live measures: **NOT RUN**.

The former134/134 and162/162 denominators decrease by one because an out-of-range DEX case no longer invents a known zero-lag value without a block anchor. Its lag is unknown and that numeric fact is omitted. Counts are not padded to retain earlier totals. This fixed self-authored suite does not cover every new regression; the new engineering tests supply the focused coverage and are not counted as extra frozen benchmark cases. No prompts were optimized using acceptance answers.

## Artifact preservation, versions and existing databases

All previous evaluation JSON/Markdown files and the original freeze/rubric/cases are preserved byte-for-byte. Their initial SHA-256 values are recorded in [previous-results-sha256.json](verification/correctness-v2/previous-results-sha256.json); final preservation checking is recorded separately. The benchmark remains v1; the scoring/detection behavior is versioned `correctness-v2` / `quality-v2`. New artifacts also record implementation-file/lock hashes. Default evaluator outputs use unique timestamped filenames; an existing explicit output path is rejected **before** case preparation or model calls.

No SQL schema change is required. New quarantine time/basis metadata and observation evidence use existing JSON columns. Reads infer time from original raw rows for pre-v2 quarantines, without rewriting those original records. Existing snapshots with previously ignored collisions must be replayed from their registered raw inputs with `import_snapshot` to populate new duplicate/conflict observations. `restore` deliberately returns the original healthy version for an injected scenario; it is not an in-place rewrite of the faulty version. Original reports/findings remain historical; new investigations use current checks and new evidence IDs.

Bounded findings include the first ten detailed records and the complete count; every observation is retained in the evidence table with its raw batch/index. This is evidence of conflicting input, not proof that the retained first valid value is economically correct. Snapshot-scoped ingestion still does not reconcile separate source revisions into one live canonical history.

## Reproduction

Implementation files changed: `sentinel/evaluation.py`, `pipeline.py`, `service.py`,
`investigation.py`, `api.py`, `ui.py`; verification helper `scripts/verify.py`;
new regression suite `tests/test_correctness_v2.py`. Handoff changes include README,
PLANS, this guide and architecture/evaluation/status/engineering/Chinese quickstart/
resume documents. No dependency, frozen-case, raw-fixture or SQL-schema changes.
New result/log directories are separate from the previous artifacts.

```powershell
cd 'D:\web3 intern\marketdata-sentinel'
uv run pytest tests/test_correctness_v2.py -m 'not postgres' -q
uv run pytest -m 'not postgres and not external and not live_llm' -q
$env:TEST_POSTGRES_URL='postgresql+psycopg://sentinel@127.0.0.1:55432/sentinel_test'
uv run pytest -m postgres -q
uv run python scripts/verify.py --postgres --output-dir docs/verification/your-new-run
$env:DATABASE_URL='sqlite:///./data/your-new-evaluation.db'
uv run python -m sentinel.evaluation --split all --baseline A
uv run python -m sentinel.evaluation --split all --baseline B
uv run python -m sentinel.evaluation --split all --baseline C
```

The last two commands create `NOT RUN` outputs until explicit `--live` and valid model configuration are supplied. Default evaluation filenames are unique; do not point a rerun at an existing result file. The portable PostgreSQL server must be running for the PostgreSQL commands; startup is documented in README.

Real model quality/latency/token/cost and model-versus-template benefit remain unknown. DEX public historical RPC collection remains unverified after the earlier403 response; offline DEX inputs are synthetic. Docker, human semantic review and trial feedback remain pending. Nothing in this repair changes those claims.
