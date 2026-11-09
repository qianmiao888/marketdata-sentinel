# Evaluation rubric v1

Defined before the first model prompt/evaluation run (2026-11-01).

1. Diagnosis: exact status equals the case oracle. A validation rejection is scored only for cases explicitly expecting rejected input.
2. Numeric correctness: every rendered metric reference must resolve to the SQL metric in the same source/window/snapshot. Decimal values are compared exactly; no tolerance masks precision errors.
3. Evidence support: every fact must reference evidence returned for that source/window/snapshot and its claim code must match the registered fact class. Mere ID existence is insufficient. Free semantic advice is not automatically certified; it has a separate manual review checklist.
4. Insufficient-evidence handling: designated cases must return insufficient_evidence, disclose missing coverage or scope, and avoid market-cause claims.
5. Trace/cost: record observed wall latency, tool/model calls and available usage. Unavailable token/fee data is unknown, never zero-cost inference.
6. Modes: A is deterministic template; B is one-shot real model; C is real model with bounded optional tools. Test adapters are engineering tests and do not count as model evaluations.

Each metric is reported as numerator/denominator. Unsupported facts and exceptions are failed cases, not removed from denominators. Results are grouped into normal, fault, and insufficient categories. B/C are NOT RUN unless explicitly enabled with live model configuration. This is a self-authored benchmark, not an external independent benchmark or production accuracy measurement.

The development split can be used for debugging. The acceptance split is frozen before the first execution; if tuning uses its answers, document contamination and create a new independently grouped acceptance version.
