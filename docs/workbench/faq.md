# 五个 FAQ / Five case FAQs

1. **少了三条记录代表市场下跌吗？** 不代表。这里人为删除了三条分钟观测，缺失不能当成零成交。两个数字是同窗口不同版本，不能据此推断市场涨跌。  
   **Do missing records indicate a market decline?** No. Missing observations are not zero-volume observations; this is a deliberately injected fault, and the comparison is between versions of one window.
2. **为什么不能直接写美元成交额？** 本案例主指标是 ETH base volume（基础资产成交数量）。USDT 计价数量另有字段，DEX 的 USDC 单侧数量也有独立口径。USD 需要明确的转换依据，不能只换标签。  
   **Why not call it dollar volume?** The primary metric is an ETH quantity. USDT quote quantity and USDC token quantity are separate metrics, not interchangeable USD labels.
3. **这是实时行情吗？** 不是。首发案例固定在 2025-01-01 00:00–01:00 UTC，使用公开历史样本与原始输入重放。  
   **Is this live market data?** No. This is a fixed historical replay for a registered UTC window.
4. **恢复到完整覆盖能证明什么？** 本次注入的缺口在恢复版本中消失，并且已实现检查未发现问题。不能证明所有数据都正确，也不能说明市场原因或生产 SLA。  
   **What does restoration establish?** It removes the injected gaps in the restored version and passes implemented checks, without proving absolute correctness or market causation.
5. **证据不足或恢复失败时怎么办？** 暂缓引用，保存来源、版本、窗口、报告与失败状态，交给工程或数据同事继续调查。不得将未执行项标成完成；对外说明仍需人工校审。  
   **What if evidence or recovery is unavailable?** Withhold citation, preserve scope and failure evidence, and escalate for investigation. Do not mark unperformed actions complete.

[完整案例](case.md) · [教程](../quickstart-zh.md) · [校审清单](glossary-review.md)
