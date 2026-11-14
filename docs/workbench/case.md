# 行情图少了三分钟：先核验，再沟通

状态：本次本地复跑完成；说明仍为待人工校审草稿。真人使用验证待完成。

## 用户问题与判断

“这个一小时的成交数量看起来较小，能否直接写成市场活跃度下降？”不能这样推断。初始版本缺失了分钟观测，不足以代表完整窗口；恢复后的数字也只能支持其对应来源、单位和窗口，不提供市场因果解释。

样本取自 Binance ETHUSDT 现货公开历史归档。三条分钟记录由本项目人为删除，是故障演练，不是交易所真实事故。时间窗固定为 **2025-01-01 00:00:00–01:00:00 UTC，左闭右开**；不是实时行情。

## 本次证据

| 项目 | 缺失版 | 恢复版 |
|---|---|---|
| 数据版本 | `s-fd9247e2bf8d19aad3323bdb` | `s-d2f57864759bf75b9284f59c` |
| 覆盖分钟 | 57/60 | 60/60 |
| 缺失分钟 | 3 | 0 |
| ETH 数量精确原值 | 6933.44030000 | 8894.44440000 |
| 来源记录的成交笔数 | 50253 | 54290 |
| 规则判断 | `observed_data_issue` | `no_issue_found_in_checks` |

缺失位置为 UTC 00:30、00:31、00:32，图中以虚线标记，不填零。页面将 ETH 数量显示为 6,933.4403 和 8,894.4444，下载保留原始精确字符串。计价资产数量另记为 USDT；ETH、USDT、USDC 与 USD 不能互换标签。

[本次运行摘要](../verification/workbench-2026-11-13/http-release/summary.json) · [缺失报告](../verification/workbench-2026-11-13/http-release/before-report.json) · [恢复后报告](../verification/workbench-2026-11-13/http-release/after-report.json) · [登记原始样本](../verification/workbench-2026-11-13/http-release/raw-samples.json)

## 实际处理与验证

通过登记的原始输入重放，得到完整原始版本；没有修改缺失版。恢复记录 `recovery-4a03ef0464134a25a88b1a112c82796d` 同时保存执行和核验状态。本次重放完成，恢复后已实现检查未发现问题，旧报告内容保持不变。

[恢复记录](../verification/workbench-2026-11-13/http-release/recovery.json) · [统一事实及结构化证据（11月14日重新导出）](../verification/export-hash-2026-11-14/historical-regenerated.json) · [中文说明](../verification/workbench-2026-11-13/http-release/communication-zh.md) · [English communication draft](../verification/workbench-2026-11-13/http-release/communication-en.md) · [问题单](../verification/workbench-2026-11-13/http-release/issue.md)

结构化证据已使用修复后的导出逻辑重新生成，11/11条内容哈希匹配；对应的历史报告、指标、范围、恢复记录及上述说明保持一致，见[重新导出核对](../verification/export-hash-2026-11-14/historical-regeneration-checks.json)。修复前的导出仅保留作历史缺陷记录，具体差异见[修复说明](../verification/export-hash-2026-11-14/README.md)。

## 仍不确定的部分与下一步

两版数字属于**同一个窗口的不同数据版本**，其差异不能写成市场成交量下跌或上涨。恢复解决了演练注入的缺口，通过当前检查不代表排除了所有数据错误，也没有建立市场原因。

对外引用前，人工核对来源、窗口、版本、数字、单位、因果、遗漏及确定程度；业务语境需要额外市场证据时继续调查。下一步用[统一真人测试脚本](human-testing.md)观察读者是否能独立找到证据、判断能否引用、解释恢复边界。目前没有真实参与者结果。

[上手教程](../quickstart-zh.md) · [五个 FAQ](faq.md) · [英文案例摘要](case-en.md) · [作品入口](index.md)
