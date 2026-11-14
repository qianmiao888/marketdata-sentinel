# MarketData Sentinel · User communication draft

DRAFT · Human editorial review pending. Not approved for publication.

Report / 报告：`0b99aade8e5847f39f41b1d5033d4575` · 2026-11-13T15:47:11.268151+00:00

## User question
这张行情图的成交数量能否作为完整时间窗口的数字引用？请检查完整性并提供依据。

## Current judgment
Data issue observed: do not cite this value as the complete-window quantity.

Public historical data with a deliberately injected fault; this is not an exchange incident.

Source / 来源：cex · ETHUSDT

Version / 版本：`s-fd9247e2bf8d19aad3323bdb`

UTC [2025-01-01T00:00:00Z, 2025-01-01T01:00:00Z)

## Key figures and evidence
| Metric | Exact value | Unit | Evidence |
|---|---|---|---|
| Observed records | 57 | candles | e-8d661b61b34ed767f638ba4e07bcf018 |
| Base-asset quantity | 6933.44030000 | ETH | e-8d661b61b34ed767f638ba4e07bcf018 |
| Quote-asset quantity | 23244130.10138200 | USDT | e-8d661b61b34ed767f638ba4e07bcf018 |
| Expected coverage | 60 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Observed coverage | 57 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Missing coverage | 3 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |

Original source / 原始来源：https://data.binance.vision/data/spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2025-01-01.zip

Input checksum / 输入校验值：`454ad76b7344bd936b7d339705a28051fa3ae6d1340c962c68fb05f90575346a`

Additional exact metrics and full evidence are retained in the structured JSON export.

## Actual handling and verification

Recovery / 恢复记录：`recovery-4a03ef0464134a25a88b1a112c82796d`

Replay / 重放：Replay completed · Verification / 核验：No issue found in executed checks

### before · `s-fd9247e2bf8d19aad3323bdb`

Report / 报告：`0b99aade8e5847f39f41b1d5033d4575`

| Metric | Exact value | Unit | Evidence |
|---|---|---|---|
| Observed records | 57 | candles | e-8d661b61b34ed767f638ba4e07bcf018 |
| Base-asset quantity | 6933.44030000 | ETH | e-8d661b61b34ed767f638ba4e07bcf018 |
| Quote-asset quantity | 23244130.10138200 | USDT | e-8d661b61b34ed767f638ba4e07bcf018 |
| Expected coverage | 60 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Observed coverage | 57 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Missing coverage | 3 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |

### after · `s-d2f57864759bf75b9284f59c`

Report / 报告：`3bb1e340dfe24a3b873148d802ac44d0`

| Metric | Exact value | Unit | Evidence |
|---|---|---|---|
| Observed records | 60 | candles | e-72c482c68748377631f96303684895f4 |
| Base-asset quantity | 8894.44440000 | ETH | e-72c482c68748377631f96303684895f4 |
| Quote-asset quantity | 29821272.00821100 | USDT | e-72c482c68748377631f96303684895f4 |
| Expected coverage | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| Observed coverage | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| Missing coverage | 0 | minutes | e-72c482c68748377631f96303684895f4 |

These are versions of the same window, not market growth or decline.

Public historical data with a deliberately injected fault; this is not an exchange incident.

## Uncertainty and next steps

Only implemented checks were evaluated; passing them does not rule out all errors or establish a market cause. Verify the source and editorial context before citation. Human usability validation is pending.

- This report is pinned to the registered input version and UTC [start, end) window; collection mode is recorded in ingestion evidence.
- Only implemented completeness, freshness, format and volume checks were evaluated; no economic cause or absolute correctness is established.
- CEX ETH/USDT and DEX token amounts are separate units; token0 volume is not dollar volume.

Next checks / 下一步：
- Inspect coverage and raw evidence for the selected UTC window.
- Use the deterministic restore task to rebuild an isolated snapshot from registered raw inputs.
