# 中文快速上手

产品定位为**规则诊断＋模型整理证据**。本轮正确性修复见 [correctness-v2.md](correctness-v2.md)：系统报告正确率可以包含模板降级，真实模型完成率/正确率单独计数，失败留在分母，降级不计为模型成功。

本项目用于排查“成交量下降是否伴随数据缺失、延迟或格式错误”。默认不需要模型密钥。Binance 固定样本是真实公开历史数据；DEX 固定样本为明确标注的合成数据。报告不解释未经证实的市场经济原因。

## Windows 启动

```powershell
cd 'D:\web3 intern\marketdata-sentinel'
uv sync --all-extras --frozen
.\scripts\start.ps1 -SkipInstall
```

打开 http://127.0.0.1:8501 ，API 文档 http://127.0.0.1:8000/docs 。首次依赖安装需要网络。脚本自动迁移、导入、创建缺失与过期场景。默认 SQLite 为便捷演示后端；真实 PostgreSQL 已独立验证，两者测试结果分开记录。

当前机器已准备 PostgreSQL 17.2（`.local/`，不入库），仅监听 `127.0.0.1:55432`。若使用它，在启动前设置：

```powershell
$env:DATABASE_URL='postgresql+psycopg://sentinel@127.0.0.1:55432/sentinel_clean'
.\scripts\start.ps1 -SkipInstall
```

如需换库先运行 `scripts/stop.ps1`，否则现有监听服务会被复用。若 PostgreSQL 已停止，启动命令见英文 README。新电脑需自行准备 PostgreSQL，或使用默认 SQLite；Docker Compose 已提供，但本环境没有 Docker，因此容器启动未执行。

## 两分钟演示

1. Overview 选择 CEX，`Demo view → Missing data`，查看 57 条 K 线、缺失三分钟和红色标记。
2. Investigate 保持 `deterministic`，点击 Run investigation，查看 `observed_data_issue`，打开 report evidence。
3. Data & Runs 打开原始样本，核对清单、checksum 和原始行。
4. 终端执行恢复：

```powershell
uv run python -m sentinel.cli restore s-fd9247e2bf8d19aad3323bdb
```

5. 切换 `Normal data`，重新调查，覆盖为 60/60，状态为 `no_issue_found_in_checks`。旧故障快照仍保留供对比；恢复返回由原始数据确定的正常快照，不会修改旧报告。

一次性完整 CLI 演示：`uv run python -m sentinel.cli demo`；输出保存在 `data/demo-result.json`。

## 验证与模型

```powershell
uv run pytest -m 'not postgres and not external and not live_llm'
uv run ruff check .
uv run ruff format --check .
$env:TEST_POSTGRES_URL='postgresql+psycopg://sentinel@127.0.0.1:55432/sentinel_test'
uv run pytest -m postgres
uv run python -m sentinel.evaluation --split all --baseline A
```

本轮实测见 `docs/verification/correctness-v2/final/results.json` 与 `evals/results/correctness-v2/`：78 项离线测试、21 项真实 PostgreSQL 测试通过。A 基线在两后端均为16/16系统报告正确，真实 B/C 未执行。旧结果仍保留在原目录；新评测默认使用带时间戳的文件名，指定已存在路径会在执行前报错。离线测试不访问公网；测试适配器不是模型成绩。

真实模型需要在环境或 `.env` 设置 provider/base URL/model/key；密钥不提交。真实模型 B/C 尚未执行。真实 DEX 的公开 RPC 后续请求 403，尚未完成真实链上采集；请提供可合法访问、支持所选历史范围的 Ethereum RPC。无此条件仍能完整演示回放、SQL 查询、确定性调查与恢复。

依赖就绪后可用 `uv run --offline python -m sentinel.cli demo` 离线回放。停止服务运行 `scripts/stop.ps1`。研究材料保持在父目录未修改。详细限制、工程取舍与简历材料见英文 README 的文档链接。
