# MarketData Sentinel

**Web3 数据核验与用户沟通工作台 / Web3 Data Verification & User Communication**

帮助 Web3 产品、运营和内容同事在引用行情数字前，检查来源与完整性、找到证据，再形成中英文说明。Python · FastAPI · SQLAlchemy/Alembic · PostgreSQL/SQLite · pytest · Streamlit。

[作品入口：两种阅读路径](docs/workbench/index.md) · [中文上手教程](docs/quickstart-zh.md) · [两分钟演示](docs/demo-script.md) · [最新验证证据](docs/verification/export-hash-2026-11-14/README.md)

![本次本地桌面核验界面](docs/verification/workbench-2026-11-13/screenshots/desktop-check.jpg)

## 一个案例，两种阅读入口

**行情图少了三分钟：检查 → 证据 → 原始输入恢复 → 同窗口对照 → 双语说明与问题单导出。**

| 入口 | 可操作的内容 | 对应材料 |
|---|---|---|
| 数据核验 / Engineering | 规则判断、覆盖与精确指标、来源、原始样本、恢复及版本对照 | [工程复盘](docs/workbench/engineering.md)、[架构](docs/architecture.md)、[本次日志](docs/verification/workbench-2026-11-13/final/results.json) |
| 用户说明 / Product & Content | 中文说明、英文摘要、问题单、FAQ、Markdown / JSON 下载 | [完整案例](docs/workbench/case.md)、[英文案例](docs/workbench/case-en.md)、[内容 brief](docs/workbench/content-brief.md)、[术语与校审](docs/workbench/glossary-review.md) |
| 高级工程 / Advanced | 原工程来源切换、查询、报告、运行记录与可选模型 | [历史正确性修复](docs/correctness-v2.md)、[评测边界](docs/evaluation.md) |

每份说明固定来源、版本与 UTC 窗口。中文、英文、页面指标和导出共用 `CommunicationBundle` 事实；改变查询参数后旧结果与下载停用。界面区分发现问题、已检查未发现问题、证据不足/失败。**检查通过不表示绝对正确，也不自动批准发布。**

## 本次复跑的固定历史案例

样本为真实公开 Binance ETHUSDT 历史归档，窗口为 **2025-01-01 00:00–01:00 UTC，[开始, 结束)**。三分钟缺失是人为注入的故障演练，**不是交易所真实事故**，不是实时行情。

| 项目 | 缺失版 | 恢复版 |
|---|---|---|
| 覆盖分钟 | 57/60 | 60/60 |
| 缺失分钟 | 3 | 0 |
| ETH 数量（阅读显示） | 6,933.4403 | 8,894.4444 |
| 规则判断 | 发现数据问题 | 已执行检查未发现问题 |

[本次实际运行摘要](docs/verification/workbench-2026-11-13/http-release/summary.json)保留报告 ID、精确原值、单位及真实 HTTP 操作。两个数字属于同一窗口的不同版本，不能写成市场涨跌。ETH、USDT、USDC 与 USD 不混用；缺失观测不补零。恢复保留旧故障版本及旧报告。

## 启动

需要 **Python 3.12 和 uv**。首次安装需要网络；依赖缓存后，固定案例可离线演示，无需模型或 RPC 密钥。

```powershell
uv sync --all-extras --frozen
.\scripts\start.ps1 -SkipInstall
```

打开[本地工作台](http://127.0.0.1:8501)及[API 文档](http://127.0.0.1:8000/docs)。停止：`.\scripts\stop.ps1`。默认 SQLite 数据位于忽略的 `data/`，日志与 PID 同目录。切换数据库前停止已有项目服务；脚本会复用已响应的本地服务。

如需独立演示数据，启动前设置：

```powershell
$env:DATABASE_URL = 'sqlite:///./data/workbench-demo.db'
.\scripts\start.ps1 -SkipInstall
```

[中文教程](docs/quickstart-zh.md)说明错误状态与完整操作。手动启动（两终端保持相同数据库环境）：

```bash
uv run alembic upgrade head
uv run python -m sentinel.cli seed
uv run python -m sentinel.cli scenario missing
uv run python -m sentinel.cli scenario stale
uv run uvicorn sentinel.api:app --host 127.0.0.1 --port 8000
# 另一终端
uv run streamlit run sentinel/ui.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

CLI 可独立重现故障、调查与恢复，并指定新证据路径，避免覆盖旧演示文件：

```powershell
uv run python -m sentinel.cli demo --output data/my-demo-result.json
```

## 验证与证据

2026-11-14 修复导出证据哈希一致性：内部引用字段在深副本中重建，登记证据原文不变。此前的输入校验与下载内容比对未覆盖导出后逐条重算 ID；本次新增检查覆盖主证据及恢复对照内的证据，见[修复验证与新产物](docs/verification/export-hash-2026-11-14/README.md)。旧验收目录保留原样。

本轮证据独立保存于 [workbench-2026-11-13](docs/verification/workbench-2026-11-13/README.md)，包括真实命令、环境、测试结果、HTTP 流程、双语导出和浏览器截图。历史记录没有充当本次结果。

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -m 'not postgres and not external and not live_llm' -q
# 提供自己的测试数据库；测试只创建并清理自身随机 schema
$env:TEST_POSTGRES_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/sentinel_test'
uv run pytest -m postgres -q
# 选择新的输出目录，保留历史验收日志
uv run python scripts/verify.py --postgres --output-dir docs/verification/my-new-run
# 服务运行后，保存真实 HTTP 工作流；已有 summary 的目录会被拒绝覆盖
uv run python scripts/capture_workbench.py --output-dir docs/verification/my-new-http
```

[原 correctness-v2](docs/correctness-v2.md)及[历史评测](docs/evaluation.md)保留各自日期、定义和限制，不与本次测试数字混用。仓库提供 [CI 配置](.github/workflows/ci.yml)，没有将本地通过声称为远程 CI 通过。

## 真实性与未完成项

- CEX 首发是公开历史样本加人为故障演练；随附 DEX 是 **synthetic** 回放。真实 DEX 历史采集仍待验证。
- 所有业务说明为草稿待人工校审；[真人使用测试](docs/workbench/human-testing.md)已准备脚本、匿名记录、问题分类与修改/复看模板，**真人使用验证待完成**。
- 规则产生诊断与精确数字，确定性模板生成本轮说明。可选模型只组织受约束证据；真实模型准确率、延迟、成本和收益未测。固定演示不依赖新 API 密钥。
- Docker Compose 尚未本轮执行；真实外部采集、远程 CI、生产部署、多人权限和商业结果均不因本轮离线测试而得到验证。
- 仅提供本机演示，无认证。没有自动推送、公开部署、社交发布、联系招聘方或提交申请。

## 工程与材料索引

[架构与数据字典](docs/architecture.md) · [工程取舍](docs/engineering-notes.md) · [本轮工程复盘](docs/workbench/engineering.md) · [来源 manifest](fixtures/README.md) · [环境配置](.env.example) · [两版岗位表述](docs/resume-bullets.md) · [面试问答](docs/workbench/interview.md) · [MIT License](LICENSE)

主体目录：`sentinel/` 为处理与服务代码，`tests/` 为自动化验证，`fixtures/` 为固定样本，`alembic/` 为既有迁移，`docs/workbench/` 为业务与招聘材料，`docs/verification/` 为分轮证据。新增恢复回执使用既有 Evidence 表，无数据库表结构迁移。
