# 导出证据哈希一致性修复 · 2026-11-14

## 缺陷与修复

`verified_run()` 的 `initial` 字典与将要导出的 `evidence` 共用字典对象。虽然登记证据在进入函数时通过哈希校验，随后在 `initial` 中补上内部计算需要的 `evidence_ids`，仍会改变导出 payload，却保留原有内容寻址 ID。数据库登记的原始 payload 未被这次临时字典修改写回。

修复为对内部所需的根证据使用 `deepcopy`，只在独立副本上重建字段。返回与导出的证据保持登记原文，包含嵌套对象。没有更改 `pipeline.digest()`、`service._register()` 或哈希定义，也没有在哈希校验时豁免 `evidence_ids`。

既有算法仍为：`e-` + `pipeline.digest({"kind": kind, "payload": payload})[:32]`。只去掉传输包装字段 `id`、`kind` 后，对实际导出 payload 重算；所有原有 payload 字段均参与计算。`recovery-...` 为执行回执 UUID，不属于内容寻址证据 ID。

## 原有检查与新增检查的区别

| 检查 | 此前覆盖 | 本次补充 |
|---|---|---|
| 登记证据输入哈希 | 在 `verified_run()` 加工前验证 | 保留原校验，防止无效输入 |
| 下载与 API/事实内容一致 | 验证下载与返回对象、数值一致 | 同一对象可能已被修改，原检查不足以证明导出哈希正确 |
| 导出后的内容 ID | 原验收没有逐条重算 | 对真实 HTTP JSON 的 `evidence[]`、`comparison.versions[].evidence[]` 全量重算并对比登记原文 |
| 双语说明与问题单 | 原有数值、单位及报告绑定检查 | 对恢复前后每个业务指标核对精确值、单位与证据引用组成的表格单元；核对来源、版本与 UTC 窗口 |

只读审计旧的 `workbench-2026-11-13/http-release/evidence.json`，其中 11 条内容寻址证据有 9 条哈希不符，见[旧产物审计](historical-export-audit.json)。旧文件没有修改；旧记录的数值/下载检查通过不代表它们通过了本次新增哈希检查。

## 本次实际结果

| 验证 | 结果 | 日志或产物 |
|---|---|---|
| 修复前新增回归 | 6 failed，33 deselected | [失败证据](red-export-hash.txt) |
| 通信模块 SQLite | 20 passed，19 deselected | [受影响测试](communication-sqlite.txt) |
| 通信模块 PostgreSQL | 19 passed，20 deselected | [受影响测试](communication-postgres.txt) |
| 完整离线回归 | 99 passed，42 deselected | [完整输出](final/offline.txt) |
| 完整 PostgreSQL 回归 | 40 passed，101 deselected | [完整输出](final/postgres.txt) |
| Ruff 与格式 | 通过 | [lint](final/lint.txt)、[format](final/format.txt) |
| 新鲜真实 HTTP 导出 | 11/11 条哈希匹配，54 项精确值/单位/引用检查通过，来源/窗口/版本一致 | [逐条检查](http/export-checks.json)、[HTTP 操作记录](http/summary.json) |
| 保存后的导出文件 | 从最终 JSON 文件重新读取并核对 11/11 条哈希；三份 Markdown 与 JSON 内文一致 | [落盘产物核对](saved-export-checks.json) |
| 同一历史报告重新导出 | 11/11 条哈希匹配；报告、指标、范围、来源、恢复记录、双语说明及问题单保持一致 | [逐项比对](historical-regeneration-checks.json)、[修复后的历史报告导出](historical-regenerated.json) |
| 旧验收记录保留 | 对修复前记录的 98 个文件逐一 SHA-256 对比 | [保留核对](preservation-after.json) |

回归覆盖 CEX 和合成 DEX，分别测试未恢复、从恢复前报告导出及从恢复后报告导出。每个场景通过真实 FastAPI 响应序列化获取实际 JSON，检查顶层与恢复对照中的所有内容寻址证据，并与登记原文直接比较。SQLite 与 PostgreSQL 均使用测试隔离库或独有随机 schema。

pytest 的一条已有 Starlette/httpx 弃用警告保留在日志中，没有变成通过数量。完整环境、执行命令和退出码见[结果记录](final/results.json)。外部采集与模型评测不属于此修复，本次未运行；没有新增真人验证声明。

## 新产物与复现

API 已按原演示库重启，修复后的产物独立写入本目录：

- [中文说明](http/communication-zh.md)、[英文说明](http/communication-en.md)、[问题单](http/issue.md)。
- [结构化导出及完整证据](http/evidence.json)、[原始样本](http/raw-samples.json)、[恢复回执](http/recovery.json)。
- [启动日志](startup.txt)、[采集验证工具输出](capture.txt)、[API 日志](api.stderr.log)、[UI 日志](ui.stderr.log)。

以下均从仓库根目录执行；输出目录使用新的名字，避免覆盖本轮及历史记录：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_communication.py -m 'not postgres' -q
# PostgreSQL 测试需提供自己的 TEST_POSTGRES_URL
.\.venv\Scripts\python.exe -m pytest tests/test_communication.py -m postgres -q
.\.venv\Scripts\python.exe scripts/verify.py --postgres --output-dir docs/verification/my-hash-checks
# 在已运行更新后 API 的条件下执行；脚本新增逐条导出哈希与事实检查
.\.venv\Scripts\python.exe scripts/capture_workbench.py --output-dir docs/verification/my-hash-http
```

本次服务继续使用 `sqlite:///./data/workbench-20261113.db`，未删除旧数据。既有下载文件保留旧字节，不会被修复自动改写；应刷新工作台、重新检查/生成后下载，或调用同一历史报告的 communication 接口重新导出。原始报告与登记证据无需重算或迁移。

[返回项目](../../../README.md) · [原验收记录](../workbench-2026-11-13/README.md)
