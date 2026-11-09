# Engineering notes and interview guide

Current scope: **rule diagnosis + model evidence organization**. The [correctness-v2 repair](correctness-v2.md) retains actual failing regressions and explains four corrected behaviors: fallback/model denominator separation, source-key conflict evidence, window-specific quarantine, and DEX interval overlap/unknown freshness. It also fixes ambiguous unresolved-evidence wording and rejects existing evaluation outputs before running cases. Final verification:78 offline/21 PostgreSQL tests passed; simulated model failures verify accounting only, not real model quality.

This is an independently implemented local development project. The incidents below are development defects, review findings, and deliberate fault exercises. None is a production incident, a customer outage, or evidence of operating a commercial service. See `implementation-status.md` for the final dated commands/results and `evaluation.md` for benchmark denominators.

## Choices that matter

- **A small data system before a model.** Parsing, exact arithmetic, missing-grid detection, scanned-block coverage and raw restore work without a key. The UI can therefore demonstrate an entire investigation/recovery flow while external services are unavailable.
- **One immutable input version per report.** A missing-data exercise creates a distinct version. Restoring produces/reuses the healthy version from its original raw input; it does not rewrite evidence under an old report.
- **PostgreSQL and a transparent local fallback.** SQLite makes the no-key demonstration easy to start; its decimal type is text-backed. The PostgreSQL path has its own integration check. PostgreSQL results must never be inferred from SQLite tests.
- **Exact application calculations over bounded SQL-selected data.** SQLAlchemy constrains queries by snapshot and `[start,end)`; Python Decimal performs the sums/change calculations with precision 100. This favors transparent precision for small historical windows. It is not a high-throughput aggregate warehouse; larger datasets would need carefully verified database aggregation/pagination.
- **Atomic batch recovery.** Normalized rows, quarantine, block coverage and checkpoint commit together. Small failed batches replay from registered raw inputs; this is intentionally simpler than a distributed checkpoint protocol. Network-stage DEX range fetching is restarted after interruption rather than durably resumed per segment.
- **Useful but constrained AI.** The live adapter genuinely accepts provider tool calls and supplies tool results. The model chooses extra reads and selects/orders supported facts. The server computes the diagnosis and rejects unsupported claims. This prevents free-form hallucinated facts but narrows what a live comparison could demonstrate; no independent economic reasoning or measured AI superiority is claimed.
- **One machine, one worker.** A local file lock and daily default schedule match daily archives. They do not provide distributed coordination, real-time freshness, continuous chain reorg repair, or a measured uptime SLA.

## Development defects and regression evidence

### Model output validation needed to trigger fallback

During implementation review, a valid-looking selection could omit `fact.checks`, the evidence supporting its diagnosis. The final report validator would then raise outside the model error handler, turning a model-format problem into a failed API request. Validation now rejects that omission inside the bounded model path and restores the complete deterministic catalog with explicit fallback status.

Reproduce the protected condition with:

```powershell
uv run pytest tests/test_investigation.py -k "omitting_diagnosis_evidence or unsupported_model_claims" -q
```

These are scripted adapter contract tests, not a successful live-model run. The output is marked `test_adapter`; actual fallback mode is deterministic.

### Empty configured prices and incomplete usage must stay unknown

Review found that optional blank price variables, as shown in a copied environment example, could reach `Decimal("")`. The settings loader now treats blanks as missing prices. A second accounting concern was a multi-call interaction where only some responses reported usage: summing just the visible calls would produce an incomplete cost presented as a complete estimate. Once a successful response lacks valid usage, the adapter retains unknown usage/cost for that investigation.

```powershell
uv run pytest tests/test_investigation.py -k "blank_price or missing_usage or actual_usage" -q
```

Costs are only computed from actual available token counts and explicitly supplied prices; the code does not hardcode current model pricing or treat unknown as zero.

### Evidence identity alone did not establish support

The initial report approach used canonical metric references, but review identified the need to compare registered evidence content as well. The implementation now retrieves registered evidence and checks its source, snapshot, UTC bounds and structured payload values. A mismatched `base_volume` can retain a valid evidence ID and still produce an insufficient-evidence fallback with no verified facts.

```powershell
uv run pytest tests/test_investigation.py -k "registered_evidence_content_mismatch or tampered_number" -q
```

While adding this check, an actual local test failed because a test switched its context to DEX but left mocked evidence labeled CEX. The failure was expected after scope enforcement. The fixture was corrected to represent DEX consistently; the validation assertion was retained. This was a test-fixture integration defect, not an upstream market-data incident.

### Browser timezone and cached-report scope

The main implementation pass found two UI problems during local browser checking: timestamp chart rendering could follow the browser's local timezone, and a previously displayed report could remain visible after the selected scope changed. `sentinel/ui.py` now defines an explicit Altair UTC scale plus UTC tooltip text, and keys cached reports by the serialized source/snapshot/start/end selection.

The appropriate check is interactive: open a report, switch snapshot or window, confirm that report is not shown for the new scope, and inspect axis/tooltip UTC times. The dated UI inspection and real screenshots belong to `implementation-status.md`/`demo-script.md`. There is no invented automated browser-regression result for these interactions.

## Deliberate fault exercises

The deterministic demo is a fault exercise with a known injected gap; it is not presented as a discovered historical exchange failure.

```powershell
uv run python -m sentinel.cli demo
```

The CLI saves actual before/after reports to `data/demo-result.json`. The missing version retains its original raw lineage. Before recovery, expected-grid/block checks report gaps and `observed_data_issue`. Restore replays registered original rows and returns the healthy version. Old fault reports remain pinned to their old input version.

The interruption test raises before the normalized transaction commits. It verifies no swaps or block coverage survived and the failed run checkpoint remained at zero, then reruns the same original input and verifies complete coverage. The zero-swap exercise independently verifies that scanning all expected blocks with no events is healthy, while unscanned blocks are a data issue.

```powershell
uv run pytest tests/test_pipeline.py -k "transaction_rolls_back or zero_swaps or idempotency_missing_restore" -q
```

External results have narrower meanings. The Binance daily archive smoke check really retrieved and checksum-validated 1,440 one-minute records. The bundled CEX sample is a smaller public historical slice. The Ethereum endpoint returned mainnet chain ID before a later HTTP 403 blocked the connected historical workflow; DEX live collection therefore remains blocked, while synthetic replay and mocked ABI/coverage contract tests are usable. Live LLM evaluation remains NOT RUN. Successful transport-contract tests do not change those statuses.

## Interview questions and code-based answers

1. **Why include the snapshot in a natural unique key?** The same market minute/event can exist in a normal and isolated fault version. Within a snapshot, CEX uses source/symbol/interval/open time; DEX uses chain/pool/block hash/transaction/log index. Including the snapshot allows reproducible comparisons without contaminating normal data. See `models.py` and `test_idempotency_missing_restore_and_isolation`.

2. **How do you distinguish no swaps from a collection gap?** Event count is insufficient. `coverage` records every successfully scanned expected block, even if `eth_getLogs` returns no events. Complete block coverage and zero swaps is valid zero activity. A missing coverage row is an unscanned interval. See `_coverage()` and `test_zero_swaps_are_not_unscanned_blocks`.

3. **What does the checkpoint guarantee if the process fails?** Normalized rows, coverage, quarantine, checkpoint and status commit in one transaction. A failure rolls them back and records a failed run separately. This implementation restarts a small batch and deduplicates its rows; it does not claim durable resume inside each network page. Explain that limit before proposing a future segment cache.

4. **Why not parse Binance timestamps with a digit-count guess?** The known spot archive date contract changes from milliseconds to microseconds at 2025-01-01. `parse_candle()` checks the manifest's declared unit against that contract, converts integer ticks without float epoch arithmetic, and validates open/close times against the registered minute and range. A wrong unit is quarantined or rejected, rather than silently producing an implausible date.

5. **Where can precision be lost?** PostgreSQL stores amounts in `NUMERIC(78,30)`, while the parser rejects unsupported precision. SQLite's custom type stores decimal strings, and raw DEX integers remain strings until Decimal normalization. SQL-selected metrics use a precision-100 context. Pandas/chart conversion can round for presentation, but exact strings remain available in API/evidence/report JSON and chart values are not saved back.

6. **How do you know a report citation actually supports a number?** Initial tool results generate registered evidence with pinned scope. `_validate_initial_evidence()` compares the retrieved payload, including numeric values, to those results. `validate_report()` then checks exact canonical facts/metric values and their references. Tests deliberately change a number while retaining the evidence ID and require rejection.

7. **What can the model do, and why does prompt injection not grant more powers?** It can select from four read tools and organize server-provided facts. `BoundTools` revalidates exact arguments, scope and allowlisted evidence IDs. There is no SQL, filesystem, shell, wallet or write tool to invoke. The prompt is an additional instruction layer; the server boundary remains the enforcement mechanism. String-based out-of-scope detection is conservative and is not claimed to understand every possible adversarial intent.

8. **What survives an unavailable model or a timeout?** Ingestion, metrics, quality, evidence, UI and deterministic reports continue to work. The requested model mode and actual deterministic fallback mode are both recorded, along with a safe failure reason. Model calls, tool steps, output tokens, request retries and total model time are bounded. No key or provider response body is included in the persisted error.

9. **What does the evaluation demonstrate?** The frozen self-authored set measures deterministic diagnosis, exact numeric references and evidence support on documented synthetic cases. Development and acceptance groups use independent source/date fragments; oracle recipes stay outside tool inputs. Actual generated artifacts report denominators and failures. B/C have no live scores without credentials, and no comparative advantage is claimed. Human semantic review remains separate.

10. **How would you add another source?** Keep the registered input/snapshot/run/evidence contracts, but write a new source parser, natural identity, precision/unit rules and coverage contract. Do not inherit the CEX minute-grid rule for sparse chain events or sum incomparable units. Extend genuine independent fixtures/tests and freeze a new evaluation version if the existing acceptance set informs tuning.

## Honest boundaries for handoff

The implementation is designed for local historical demonstrations and bounded reads. It has no production user feedback, external independent benchmark, continuously observed multi-day SLA, fully verified live DEX ingestion, or measured live-model benefit. A successful real PostgreSQL integration run is a distinct result from offline SQLite tests; container image execution also needs its own actual Docker run. Future improvements should be driven by concrete failures or real trial feedback, rather than filling these gaps with claimed experience.
