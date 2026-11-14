# MarketData Sentinel · 用户说明草稿

草稿 · 待人工校审，尚未批准对外发布。

Report / 报告：`7843c9437bcd41288d37f2d1607345a0` · 2026-11-13T15:45:24.038819+00:00

## 用户问题
这张行情图的成交数量能否作为完整时间窗口的数字引用？请检查完整性并提供依据。

## 当前判断
发现数据问题：不能将当前数字直接作为完整窗口的成交数量引用。

真实公开历史数据，人为构造的故障演练；不是交易所真实事故。

Source / 来源：cex · ETHUSDT

Version / 版本：`s-fd9247e2bf8d19aad3323bdb`

UTC [2025-01-01T00:00:00Z, 2025-01-01T01:00:00Z)

## 关键数字与证据
| 指标 | 精确原值 | 单位 | 证据 |
|---|---|---|---|
| 观测记录 | 57 | candles | e-8d661b61b34ed767f638ba4e07bcf018 |
| 基础资产成交数量 | 6933.44030000 | ETH | e-8d661b61b34ed767f638ba4e07bcf018 |
| 计价资产成交数量 | 23244130.10138200 | USDT | e-8d661b61b34ed767f638ba4e07bcf018 |
| 来源记录的成交笔数 | 50253 | trades | e-8d661b61b34ed767f638ba4e07bcf018 |
| 预期覆盖 | 60 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 实际覆盖 | 57 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 缺失覆盖 | 3 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 相对参考时钟的延迟 | 0 | seconds relative to reference clock | e-e1beec2ca77f32534e6e9cbdee0feee2 |
| 窗口内隔离记录 | 0 | rows | e-e1beec2ca77f32534e6e9cbdee0feee2 |

Original source / 原始来源：https://data.binance.vision/data/spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2025-01-01.zip

Input checksum / 输入校验值：`454ad76b7344bd936b7d339705a28051fa3ae6d1340c962c68fb05f90575346a`

## 实际处理与验证

Recovery / 恢复记录：`recovery-1fb032ba7e934c95bad1e6055d52f0fb`

Replay / 重放：重放已完成 · Verification / 核验：已执行检查未发现问题

### before · `s-fd9247e2bf8d19aad3323bdb`

Report / 报告：`7843c9437bcd41288d37f2d1607345a0`

| 指标 | 精确原值 | 单位 | 证据 |
|---|---|---|---|
| 观测记录 | 57 | candles | e-8d661b61b34ed767f638ba4e07bcf018 |
| 基础资产成交数量 | 6933.44030000 | ETH | e-8d661b61b34ed767f638ba4e07bcf018 |
| 计价资产成交数量 | 23244130.10138200 | USDT | e-8d661b61b34ed767f638ba4e07bcf018 |
| 来源记录的成交笔数 | 50253 | trades | e-8d661b61b34ed767f638ba4e07bcf018 |
| 预期覆盖 | 60 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 实际覆盖 | 57 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 缺失覆盖 | 3 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 相对参考时钟的延迟 | 0 | seconds relative to reference clock | e-e1beec2ca77f32534e6e9cbdee0feee2 |
| 窗口内隔离记录 | 0 | rows | e-e1beec2ca77f32534e6e9cbdee0feee2 |

### after · `s-d2f57864759bf75b9284f59c`

Report / 报告：`54dcd281f76247f6847761c6f9158346`

| 指标 | 精确原值 | 单位 | 证据 |
|---|---|---|---|
| 观测记录 | 60 | candles | e-72c482c68748377631f96303684895f4 |
| 基础资产成交数量 | 8894.44440000 | ETH | e-72c482c68748377631f96303684895f4 |
| 计价资产成交数量 | 29821272.00821100 | USDT | e-72c482c68748377631f96303684895f4 |
| 来源记录的成交笔数 | 54290 | trades | e-72c482c68748377631f96303684895f4 |
| 预期覆盖 | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| 实际覆盖 | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| 缺失覆盖 | 0 | minutes | e-72c482c68748377631f96303684895f4 |
| 相对参考时钟的延迟 | 0 | seconds relative to reference clock | e-6fe206bba5472c82506990027dfde8aa |
| 窗口内隔离记录 | 0 | rows | e-6fe206bba5472c82506990027dfde8aa |
| 相邻子窗口变化（待调查） | 56.40967363971576444606342890530705181891866367362103517451303334381521990686688107832667577864331178 | % (equal adjacent subwindows) | e-72c482c68748377631f96303684895f4 |

这是同一时间窗口的数据版本对照，不能解释为市场涨跌。

真实公开历史数据，人为构造的故障演练；不是交易所真实事故。

## 不确定性与下一步

仅执行已实现的检查；通过不代表排除全部错误，也不证明市场因果。引用前继续核对来源与使用语境，完成数字、单位、遗漏、因果及确定程度的双语校审。真人使用验证待完成。

- This report is pinned to the registered input version and UTC [start, end) window; collection mode is recorded in ingestion evidence.
- Only implemented completeness, freshness, format and volume checks were evaluated; no economic cause or absolute correctness is established.
- CEX ETH/USDT and DEX token amounts are separate units; token0 volume is not dollar volume.

Next checks / 下一步：
- Inspect coverage and raw evidence for the selected UTC window.
- Use the deterministic restore task to rebuild an isolated snapshot from registered raw inputs.

---

# MarketData Sentinel · User communication draft

DRAFT · Human editorial review pending. Not approved for publication.

Report / 报告：`7843c9437bcd41288d37f2d1607345a0` · 2026-11-13T15:45:24.038819+00:00

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

Recovery / 恢复记录：`recovery-1fb032ba7e934c95bad1e6055d52f0fb`

Replay / 重放：Replay completed · Verification / 核验：No issue found in executed checks

### before · `s-fd9247e2bf8d19aad3323bdb`

Report / 报告：`7843c9437bcd41288d37f2d1607345a0`

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

Report / 报告：`54dcd281f76247f6847761c6f9158346`

| Metric | Exact value | Unit | Evidence |
|---|---|---|---|
| Observed records | 60 | candles | e-72c482c68748377631f96303684895f4 |
| Base-asset quantity | 8894.44440000 | ETH | e-72c482c68748377631f96303684895f4 |
| Quote-asset quantity | 29821272.00821100 | USDT | e-72c482c68748377631f96303684895f4 |
| Source-reported trades | 54290 | trades | e-72c482c68748377631f96303684895f4 |
| Expected coverage | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| Observed coverage | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| Missing coverage | 0 | minutes | e-72c482c68748377631f96303684895f4 |
| Lag relative to reference clock | 0 | seconds relative to reference clock | e-6fe206bba5472c82506990027dfde8aa |
| Quarantined rows in window | 0 | rows | e-6fe206bba5472c82506990027dfde8aa |
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
