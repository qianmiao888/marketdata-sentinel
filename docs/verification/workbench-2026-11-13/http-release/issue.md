# 问题单 · 0b99aade8e5847f39f41b1d5033d4575

状态：草稿待校审；真人使用验证待完成。

## 现象
这张行情图的成交数量能否作为完整时间窗口的数字引用？请检查完整性并提供依据。

## 当前判断
发现数据问题：不能将当前数字直接作为完整窗口的成交数量引用。

## 已知影响范围
仅限来源 cex、版本 `s-fd9247e2bf8d19aad3323bdb`、UTC [2025-01-01T00:00:00Z, 2025-01-01T01:00:00Z)；不外推至整个交易所或市场。

## 复现步骤
1. 启动工作台并选择上述来源、版本和 UTC 窗口。
2. 运行数据检查，查看覆盖情况及登记证据。
3. 如需复现恢复，点击从原始输入恢复，保持相同时间窗，再对照报告。

## 实际处理与验证
记录 `recovery-4a03ef0464134a25a88b1a112c82796d`；重放：重放已完成；核验：已执行检查未发现问题。

## 证据
| 指标 | 精确原值 | 单位 | 证据 |
|---|---|---|---|
| 观测记录 | 57 | candles | e-8d661b61b34ed767f638ba4e07bcf018 |
| 基础资产成交数量 | 6933.44030000 | ETH | e-8d661b61b34ed767f638ba4e07bcf018 |
| 计价资产成交数量 | 23244130.10138200 | USDT | e-8d661b61b34ed767f638ba4e07bcf018 |
| 预期覆盖 | 60 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 实际覆盖 | 57 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 缺失覆盖 | 3 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |

## 待解决项
人工内容校审待完成；真人使用验证待完成；检查范围以外的数据错误和市场原因尚未排除。

## 用户说明
# MarketData Sentinel · 用户说明草稿

草稿 · 待人工校审，尚未批准对外发布。

Report / 报告：`0b99aade8e5847f39f41b1d5033d4575` · 2026-11-13T15:47:11.268151+00:00

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
| 预期覆盖 | 60 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 实际覆盖 | 57 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 缺失覆盖 | 3 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |

Original source / 原始来源：https://data.binance.vision/data/spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2025-01-01.zip

Input checksum / 输入校验值：`454ad76b7344bd936b7d339705a28051fa3ae6d1340c962c68fb05f90575346a`

其他精确指标与完整证据保留在结构化 JSON 导出中。

## 实际处理与验证

Recovery / 恢复记录：`recovery-4a03ef0464134a25a88b1a112c82796d`

Replay / 重放：重放已完成 · Verification / 核验：已执行检查未发现问题

### before · `s-fd9247e2bf8d19aad3323bdb`

Report / 报告：`0b99aade8e5847f39f41b1d5033d4575`

| 指标 | 精确原值 | 单位 | 证据 |
|---|---|---|---|
| 观测记录 | 57 | candles | e-8d661b61b34ed767f638ba4e07bcf018 |
| 基础资产成交数量 | 6933.44030000 | ETH | e-8d661b61b34ed767f638ba4e07bcf018 |
| 计价资产成交数量 | 23244130.10138200 | USDT | e-8d661b61b34ed767f638ba4e07bcf018 |
| 预期覆盖 | 60 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 实际覆盖 | 57 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |
| 缺失覆盖 | 3 | minutes | e-8d661b61b34ed767f638ba4e07bcf018 |

### after · `s-d2f57864759bf75b9284f59c`

Report / 报告：`3bb1e340dfe24a3b873148d802ac44d0`

| 指标 | 精确原值 | 单位 | 证据 |
|---|---|---|---|
| 观测记录 | 60 | candles | e-72c482c68748377631f96303684895f4 |
| 基础资产成交数量 | 8894.44440000 | ETH | e-72c482c68748377631f96303684895f4 |
| 计价资产成交数量 | 29821272.00821100 | USDT | e-72c482c68748377631f96303684895f4 |
| 预期覆盖 | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| 实际覆盖 | 60 | minutes | e-72c482c68748377631f96303684895f4 |
| 缺失覆盖 | 0 | minutes | e-72c482c68748377631f96303684895f4 |

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

