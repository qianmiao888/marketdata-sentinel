# 中英术语与校审清单

| 中文 | English | 使用约束 |
|---|---|---|
| 数据版本 | Data version / pinned snapshot | 固定输入及变换；不能与另一个时间段混淆 |
| 时间窗 | UTC window [start, end) | UTC、含开始、不含结束 |
| 分钟 K 线 | One-minute candle | 一条分钟观测；不是一笔成交 |
| 基础资产成交数量 | Base-asset quantity / base volume | 本案例为 ETH，不是 USD |
| 计价资产成交数量 | Quote-asset quantity / quote volume | ETHUSDT 的单位为 USDT |
| 单侧绝对数量 | Single-side absolute quantity | 合成 DEX 样本 token0 为 USDC，不是美元成交额 |
| 缺失观测 | Missing observation | 未采到不等于真实零值 |
| 原始输入重放 | Registered raw-input replay | 重新生成或复用完整版本，不修改旧报告 |
| 发现数据问题 | Data issue observed | 已执行检查支持的判断，不外推交易所事故 |
| 已执行检查未发现问题 | No issue found in executed checks | 不等于绝对正确或批准发布 |
| 证据不足 | Insufficient evidence | 暂缓引用，不自动补正常结论 |
| 人为故障演练 | Deliberately injected fault exercise | 原始历史数据真实，故障不是真实事故 |

## 每次对外使用前逐项填写

- [ ] **数字**：中文、英文、页面及下载与同一报告精确值一致；展示舍入不改变原值。
- [ ] **单位**：ETH、USDT、USDC、USD 不混用；成交笔数与分钟记录数分开。
- [ ] **来源与版本**：provider、symbol、UTC 时间窗、版本和证据 ID 齐全。
- [ ] **因果**：同窗口版本差未写成市场涨跌，演练未写成交易所真实事故。
- [ ] **遗漏**：翻译保留处理状态、限制、草稿标记和下一步。
- [ ] **确定程度**：检查通过未写成排除全部错误；失败、未知和待验证保持原义。
- [ ] **动作**：仅有实际恢复记录才写已执行；不把重放完成等同于恢复核验通过。
- [ ] **真实性**：不声称真实链上采集、实时、生产、模型有效或商业收益。

本次已完成自动化数值/引用一致性检查及代理内容自检；以上复选框留给真实人工校审，不作为已签署记录。

人工校审人（自愿）：____　日期：____　报告 ID：____　问题/修改：____　复核：____

[内容 brief](content-brief.md) · [真人测试](human-testing.md)
