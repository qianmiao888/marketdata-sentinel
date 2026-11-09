# Evaluation and evidence limits

## Current scoring: correctness-v2

The product is **rule diagnosis + model evidence organization**. Current definitions,
regression evidence and limits are in [correctness-v2.md](correctness-v2.md).
System report correctness includes successful template fallback. B/C live completion
and correctness are separate: timeout, tool, format, budget and fallback cases remain
in all-attempt model denominators. Test adapters never become live scores.
Correctness among completed models is also reported, explicitly conditional.

Final artifacts are `evals/results/correctness-v2/A-all-sqlite-final.json` and
`A-all-postgres-final.json`: both system reports16/16, numeric133/133,
supported facts161/161 and unknown handling2/2 on the unchanged16-case v1 suite.
B/C artifacts remain NOT RUN; genuine model scores are unknown. The omitted lag
metric reflects an unanchored/outside DEX interval now having unknown freshness,
instead of an invented zero. Model measures for A are not applicable.

Original outputs and frozen cases/rubric remain byte-identical. All later sections
on this page describe historical executions, including their earlier134/134 and
162/162 counts; those are not current or genuine model results. New evaluations use
unique timestamped filenames and reject an existing explicit path before execution.
New artifacts record scoring version and implementation/lock checksums. These known
acceptance cases remain a regression suite, not a new independent benchmark.

The rubric and sixteen-case v1 manifest were frozen before the first execution.
`evals/freeze.json` records SHA-256 of the rubric and oracle manifest; the runner
refuses to execute if either changes. This is a self-authored benchmark, not an
external independent benchmark, a production accuracy estimate, or proof of AI value.

The target was forty cases. The implemented set contains eight development cases
and eight frozen acceptance cases. They cover normal inputs, missing coverage,
stale tails, malformed numeric values, duplicate and out-of-order ingestion,
legitimate zero volume/zero swaps, and unavailable time ranges. Additional 429,
timeout, timestamp, unit, model/tool-failure and tool-permission behaviors belong to
the engineering test suite; they are not counted as independent model benchmark
cases. Repeating a supported mutation to fill the forty-case target would inflate
the denominator.

Development uses independent synthetic CEX dates in February 2025. Acceptance uses
independent synthetic DEX dates in March 2025. No raw fragment or source/date group
crosses the split. All synthetic values/hashes are explicitly marked synthetic and
do not claim historical chain observations. This grouping also limits conclusions:
the frozen split tests DEX behavior and cannot establish generalization to unseen
CEX history. An expanded benchmark should add independently sourced dates and fault
families, then freeze a new version before model tuning.

The oracle's recipe and expected diagnosis remain in evaluator-only files. The
investigator receives only a constant neutral question, a source, an opaque snapshot
ID and UTC window. Registered tool responses do not reveal scenario names or oracle
labels. The raw transform is lineage for deterministic recovery, not an investigator
input. The LLM has no filesystem tool that could read `evals/`.

Run from the project directory after dependency installation:

```powershell
uv run python -m sentinel.evaluation --split development --baseline A
uv run python -m sentinel.evaluation --split acceptance --baseline A
uv run python -m sentinel.evaluation --split all --baseline A
uv run python -m sentinel.evaluation --split all --baseline B
uv run python -m sentinel.evaluation --split all --baseline C
```

The last two commands write `NOT RUN` artifacts without contacting a model. For
real model calls, configure the provider variables documented in `.env.example`
and add `--live`. A is the deterministic rules/template baseline; B receives the
same initial ingestion, quality and metric information in a single model call;
C receives the same information and may choose additional bounded read-only
queries. C's extra queries are logged. A test adapter is never a B/C live score.

Results are generated under `evals/results/` as JSON and Markdown. Each automatic
measure retains numerator/denominator, failures, source snapshot, latency, trace,
actual available model calls/usage/fees, environment and timestamp. The automated
checks compare diagnosis against the frozen oracle, metric values against same-scope
SQL results, and metric/quality claims against returned evidence payload contents.
An evidence ID's existence alone is insufficient. Unknown token and fee data remains
`null`/unknown. Unsupported claims and exceptions stay in failure denominators.

Human semantic review is a separate pending task, even when mechanical checks pass.
Review each failed case and a representative normal/fault/insufficient sample:

- Does the conclusion stay within the executed checks and identify missing evidence?
- Does it avoid explaining market behavior with an invented economic cause?
- Do units, UTC range, data version and references convey the actual observation?
- Are recommendations useful and within the read-only investigation boundary?
- Does fallback/model-unavailable labeling remain clear?

Do not adjust prompts against acceptance answers and keep claiming an untouched
freeze. If acceptance results inform tuning, record the contamination and create
a new independent acceptance version. Do not claim C outperforms A/B unless actual
like-for-like live results support that statement.

## Recorded execution

On 2026-11-01, A ran using Python 3.12 and the explicit SQLite evaluation database
(`sqlite:///./data/evaluation.db`). The development run scored diagnosis 8/8,
numeric references 77/77 and supported facts 92/92. The first frozen acceptance
execution scored diagnosis 8/8, numeric references 62/62 and supported facts 75/75.
No prompt adjustments were made using acceptance outputs. The combined artifact
records diagnosis 16/16, numeric references 139/139, supported facts 167/167 and
insufficient-evidence handling 2/2. See generated
[`A-all.md`](../evals/results/A-all.md) and
[`A-all.json`](../evals/results/A-all.json) for exact environment, per-case trace,
snapshot IDs, latency and denominators. These are deterministic replay results;
they do not replace the separately reported real PostgreSQL integration checks.

B and C were not executed against a real model. Their artifacts explicitly say
`NOT RUN`. Their scores and any comparative benefit remain unknown. The implemented
model interface selects/reorders a server-validated fact catalog and uses a
diagnosis supported by deterministic checks; this benchmark tests evidence-safe
organization and optional query behavior rather than unrestricted causal reasoning.
Human semantic review remains pending. Initial development scoring revealed that
the grader needed to recognize the newly implemented quality-check summary fact;
this evaluator integration bug was fixed against development outputs before the
first acceptance execution. Neither the frozen case expectations nor rubric were
changed.

## Post-smoke-test correctness correction

Actual browser inspection later exposed a comparison being displayed despite incomplete
coverage. The metric service now suppresses percentage change for incomplete coverage
and unequal CEX half-minute subdivisions (`insufficient_samples`), with a regression
test. This was a data-rule correction found during the demo, not a prompt change
selected from acceptance answers. The earlier combined artifact is preserved as
`A-initial-before-comparison-fix.json`/`.md`. A rerun of the unchanged frozen suite
produced diagnosis **16/16**, numeric references **134/134**, supported facts
**162/162**, and unknown handling **2/2**. Five percentage facts are intentionally
absent, so their numerator and denominator both decreased. The latest `A-all` files
represent the delivered code; the separate development/acceptance artifacts describe
the earlier run. Repeated regression execution on a known self-authored suite is not
a new independent benchmark. Human semantic review remains pending.
