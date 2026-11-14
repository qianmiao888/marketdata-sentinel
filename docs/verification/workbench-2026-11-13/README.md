# 本轮运行与验证证据 · 2026-11-13

此目录只记录本轮本机执行，不借用历史通过数量。固定历史样本的 UTC 窗口与当前运行日期分开；运行时间见各 JSON。真人使用验证待完成。

| 验证 | 本次结果 | 证据 |
|---|---|---|
| Python / 系统 / 依赖 | Python 3.12.9 / Windows 11，版本逐项记录 | [环境与命令](final/results.json) |
| 离线回归 | **93 passed，36 deselected**，1 条依赖弃用警告 | [完整输出](final/offline.txt) |
| 真实 PostgreSQL 集成 | **34 passed，95 deselected**，PostgreSQL 17.2 | [完整输出](final/postgres.txt) |
| Ruff lint / format | 通过 | [lint](final/lint.txt)、[format](final/format.txt) |
| 既有 CLI 故障与恢复 | 实际执行，写入独立产物 | [CLI JSON](demo-result.json)、[控制台](demo-console.json) |
| 新增 HTTP 工作流 | 检查 → 恢复 → 固定窗口对照 → 说明 / 问题单，旧报告内容未改变 | [操作与摘要](http-release/summary.json)、[恢复回执](http-release/recovery.json) |
| 业务说明及结构化证据 | 从同一事实生成，精确原值保留 | [中文](http-release/communication-zh.md)、[英文](http-release/communication-en.md)、[问题单](http-release/issue.md)、[事实与证据](http-release/evidence.json) |
| 真实浏览器流程 | 本机代理操作，桌面 1440×1000、窄屏 390×844；非真人研究 | [记录](browser.json)、[截图](#界面截图) |
| 浏览器实际下载 | 三个按钮取回文件，并逐项比对 JSON 与说明 | [核对结果](delivery-checks.json)、[说明](browser-downloads-final/communication.md)、[问题单](browser-downloads-final/issue.md)、[JSON](browser-downloads-final/evidence.json) |
| 文档链接 / 英文篇幅 | 仓库内相对目标与 150–250 词要求核对 | [核对结果](delivery-checks.json) |

## 实际命令与运行隔离

命令从仓库根目录执行。下面是本轮演示使用的独立 SQLite 文件名，不要求读者使用原电脑目录：

```powershell
$env:DATABASE_URL = 'sqlite:///./data/workbench-20261113.db'
$env:UV_OFFLINE = '1'
uv run alembic upgrade head
uv run python -m sentinel.cli demo --output docs/verification/workbench-2026-11-13/demo-result.json
.\scripts\start.ps1 -SkipInstall
uv run python scripts/capture_workbench.py --output-dir docs/verification/my-new-http
uv run python scripts/verify.py --postgres --output-dir docs/verification/my-new-checks
```

最终 lint / format / pytest 通过命令记录在 `final/results.json`。PostgreSQL 测试显式设置 `TEST_POSTGRES_URL`，在原本机的便携 PostgreSQL 17.2 上使用各测试独有随机 schema，未删除原数据库。连接参数不要求随仓库分发；新机器自行提供测试库。

[迁移日志](migration.txt)、[本次启动输出](startup-release.txt)、[API 日志](api.stderr.log)、[UI 日志](ui.stderr.log)保留执行状态。此前 `http/`、`http-final/`、`browser-downloads/` 和顶层初轮测试日志保留为本轮开发中间记录；**最终验收以 `final/`、`http-release/` 和 `browser-downloads-final/` 为准**。

最终完整回归后，仅调整 UI 的 FAQ 网页链接与输入校验详情；又执行 lint、格式及文档/下载核对，见[交付核对](delivery-checks.json)。没有为静态文案重复全量测试。

## 界面截图

- [桌面检查](screenshots/desktop-check.jpg)：判断、来源标记和精确指标入口。
- [同窗口恢复对照](screenshots/desktop-recovery.jpg)：重放与核验状态、保留的两版数据。
- [英文预览](screenshots/desktop-english.jpg)：草稿状态、当前判断和版本信息。
- [窄屏](screenshots/narrow.jpg)：指标纵向排列，文字可读；宽证据表在组件内横向查看，整页宽度未溢出。
- [参数变化](screenshots/scope-change.jpg)、[无效窗口](screenshots/invalid-window.jpg)：旧报告和下载撤下。
- [高级工程 DEX](screenshots/advanced-dex.jpg)：合成数据标签保留。

截图均来自本次实际本地界面，没有生成或冒充其他设备截图。视口检查不代表在实体手机上测试。

## 仍未执行或未得到验证

真人使用测试、人工签署的双语校审、真实链上采集、真实模型评测、Docker、远程 CI、公网生产运行与商业效果。外部数据采集测试本轮未执行。自动化故障注入不等于外部服务实际故障，代理检查不等于真人反馈。

开发中修正记录见[development-notes](development-notes.md)。[返回作品入口](../../workbench/index.md)。
