# MarketData Sentinel · User communication draft

DRAFT · Human editorial review pending. Not approved for publication.

Report / 报告：`39d9387302ec43fcbf96b6983d173273` · 2026-11-13T15:44:54.504792+00:00

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
| Source-reported trades | 50253 | trades | e-8d661b61b34ed767f638ba4e07bcf018 |
| Expected coverage | 60 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Observed coverage | 57 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Missing coverage | 3 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Lag relative to reference clock | 0 | seconds relative to reference clock | e-e1beec2ca77f32534e6e9cbdee0feee2 |
| Quarantined rows in window | 0 | rows | e-e1beec2ca77f32534e6e9cbdee0feee2 |

Original source / 原始来源：https://data.binance.vision/data/spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2025-01-01.zip

Input checksum / 输入校验值：`454ad76b7344bd936b7d339705a28051fa3ae6d1340c962c68fb05f90575346a`

## Actual handling and verification

Recovery / 恢复记录：`recovery-4f4abe92f2e14ac783443df354e55d89`

Replay / 重放：Replay completed · Verification / 核验：No issue found in executed checks

### before · `s-fd9247e2bf8d19aad3323bdb`

Report / 报告：`39d9387302ec43fcbf96b6983d173273`

| Metric | Exact value | Unit | Evidence |
|---|---|---|---|
| Observed records | 57 | candles | e-8d661b61b34ed767f638ba4e07bcf018 |
| Base-asset quantity | 6933.44030000 | ETH | e-8d661b61b34ed767f638ba4e07bcf018 |
| Quote-asset quantity | 23244130.10138200 | USDT | e-8d661b61b34ed767f638ba4e07bcf018 |
| Source-reported trades | 50253 | trades | e-8d661b61b34ed767f638ba4e07bcf018 |
| Expected coverage | 60 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Observed coverage | 57 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Missing coverage | 3 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| Lag relative to reference clock | 0 | seconds relative to reference clock | e-e1beec2ca77f32534e6e9cbdee0feee2 |
| Quarantined rows in window | 0 | rows | e-e1beec2ca77f32534e6e9cbdee0feee2 |

### after · `s-d2f57864759bf75b9284f59c`

Report / 报告：`46537dbd8faf47b4be911220ce9c8700`

| Metric | Exact value | Unit | Evidence |
|---|---|---|---|
| Observed records | 60 | candles | e-72c482c68748377631f96303684895f4 |
| Base-asset quantity | 8894.44440000 | ETH | e-72c482c68748377631f96303684895f4 |
| Quote-asset quantity | 29821272.00821100 | USDT | e-72c482c68748377631f96303684895f4 |
| Source-reported trades | 54290 | trades | e-72c482c68748377631f96303684895f4 |
| Expected coverage | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| Observed coverage | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| Missing coverage | 0 | minutes | e-72c482c68748377631f96303684895f4 |
| Lag relative to reference clock | 0 | seconds relative to reference clock | e-c5bf7002c19f888d7d6827a19f6c0ee0 |
| Quarantined rows in window | 0 | rows | e-c5bf7002c19f888d7d6827a19f6c0ee0 |
| Adjacent-subwindow change (requires investigation) | 56.40967363971576444606342890530705181891866367362103517451303334381521990686688107832667577864331178 | % (equal adjacent subwindows) | e-72c482c68748377631f96303684895f4 |

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
