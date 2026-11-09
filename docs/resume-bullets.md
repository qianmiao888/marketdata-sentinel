# Resume material — evidence limited to this implementation

Personal project, independent development with AI coding assistance. Start: November 2026. This is not company employment or a production service. Choose the relevant two or three bullets and be prepared to explain/change the code. Do not claim real-model gains, production uptime, users or business savings.

## Data engineering

中文：使用 Python、FastAPI、SQLAlchemy/Alembic 和 PostgreSQL 构建 Web3 市场数据工作台；实现 Binance ETHUSDT 历史归档采集、校验清单、精确数值存储、幂等写入、事务检查点和原始数据恢复，实测完整一天1,440条 K 线导入与覆盖校验。

English: Built a Python/FastAPI market-data workbench with PostgreSQL and Alembic, including verified Binance archives, precise numeric storage, idempotent ingestion, atomic checkpoints and raw-input recovery; exercised a full 1,440-candle public daily archive.

中文：设计基于固定快照的数据质量与证据链，通过隔离故障回放复现三分钟缺口，覆盖从57/60恢复为60/60；分别计算 CEX ETH/USDT 与单池 DEX token 数量口径。链上演示为合成数据，真实 RPC 采集仍待接入验证。

English: Implemented version-pinned quality checks and evidence lookup; reproduced a three-minute gap and restored coverage from 57/60 to 60/60 using registered raw inputs. Kept CEX and DEX units separate; the chain replay uses labeled synthetic data, with real RPC ingestion still pending verification.

## AI application engineering

定位：**规则诊断＋模型整理证据** / **Rule diagnosis + model evidence organization**. System report correctness includes successful deterministic fallback; live model completion/correctness must be reported separately and failures remain in their denominators.

中文：实现可配置的工具调用模型适配器及四个服务端绑定来源、时间窗与快照的只读调查工具；结构化报告关联精确指标和证据内容，支持预算限制、错误降级和持久化轨迹。默认确定性模式可无密钥运行；未将测试适配器写成真实模型成绩。

English: Implemented a configurable tool-calling model adapter with four server-bound read-only investigation tools, validated metric/evidence reports, call budgets, explicit fallback and persisted traces. Delivered a key-free deterministic mode; live model evaluation remains unexecuted.

中文：制定并冻结16个自建合成评测场景（开发/验收各8个），通过执行产物自动生成系统报告与独立模型统计；本轮确定性 A 基线在 SQLite 与 PostgreSQL 均为系统报告16/16、数值引用133/133、证据支持161/161。B/C 真实模型仍未执行；这些结果不代表模型准确率。

English: Froze16 self-authored synthetic scenarios (8 development/8 acceptance) and separated system report scoring from live-model completion/correctness. The current deterministic baseline scored16/16 system reports,133/133 numeric references and161/161 evidence-supported facts on both SQLite and PostgreSQL; genuine B/C model evaluations remain unexecuted.

## Testing / automation

中文：覆盖时间戳单位、Decimal/int256 边界、幂等、事务回滚续跑、零成交与未扫描覆盖、API/工具权限和模型降级；建立离线测试与独立 PostgreSQL 集成测试，并配置 GitHub Actions 的 lint、格式和 PostgreSQL 服务验证。具体测试数量以 `docs/verification/` 的最终日志为准。

English: Tested timestamp-unit contracts, Decimal/int256 bounds, atomic rollback/recovery, zero-event coverage, API/tool permissions and model fallback. Added isolated-schema PostgreSQL integration tests and a CI workflow for lint, formatting, offline tests and PostgreSQL; actual counts are retained in verification logs.

## Do not add yet

- Real LLM B/C success rates, token/cost/latency gains, or C-over-A/B benefits.
- Real on-chain collection or production reorganization handling.
- Forty-case benchmark, external benchmark validation, human semantic review, or user feedback.
- Multi-day operation, uptime/SLA, commercial customers, money saved, team review or merged open-source contribution.

Suggested candidate header (verify dates against your calendar): **AI undergraduate, class of 2028 · Mainland China / UTC+8 · available 5 days/week for 6+ months from the 2027 winter break**. CET-6 is not automatically fluent interview English. Explain the code and use the English README/demo as communication evidence; no offer outcome is promised.
