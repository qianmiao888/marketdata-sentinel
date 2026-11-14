"""Chinese-first evidence and communication workbench; advanced UI remains available."""

import json
import os
import runpy
from decimal import Decimal
from pathlib import Path

import altair as alt
import httpx
import pandas as pd
import streamlit as st

from sentinel.communication import LABELS, data_notice, execution_label
from sentinel.workbench_state import current_bundle, scope_key

API = os.getenv("SENTINEL_API_URL", "http://127.0.0.1:8000").rstrip("/")
st.set_page_config(
    page_title="MarketData Sentinel · 数据核验与用户沟通", page_icon="◈", layout="wide"
)
st.markdown(
    """<style>
.block-container {max-width:1200px;padding-top:2rem}
[data-testid="stMetric"] {background:#f1f5f9;border-radius:10px;padding:12px}
[data-testid="stMetricValue"] {font-size:clamp(1.1rem,2vw,1.7rem)}
@media(max-width:640px) {.block-container {padding:1rem} [data-testid="stHorizontalBlock"] {flex-wrap:wrap}}
</style>""",
    unsafe_allow_html=True,
)
entry = st.sidebar.radio(
    "阅读入口 / Workspace",
    ["数据核验 / Engineering", "用户说明 / Product & Content", "高级工程 / Advanced"],
)
if entry == "高级工程 / Advanced":
    runpy.run_path(str(Path(__file__).with_name("ui_engineering.py")))
    st.stop()

st.title("◈ MarketData Sentinel")
st.caption("Web3 数据核验与用户沟通工作台 / Web3 Data Verification & User Communication")
st.write("引用行情数字前，先检查来源与完整性，再给出有证据的说明。")
st.info(
    "首发案例：真实公开历史数据 + 人为删去三分钟的故障演练。不是交易所真实事故，也不是实时行情。"
)


def request(path, *, body=None, params=None):
    try:
        with httpx.Client(timeout=httpx.Timeout(90, connect=5), trust_env=False) as client:
            response = (
                client.post(API + path, json=body)
                if body is not None
                else client.get(API + path, params=params)
            )
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError):
        st.error(
            "请求失败，当前不足以判断。请确认 API 已启动、查询有效后重试；不会自动给出正常结论。 / Request failed; evidence is unavailable."
        )
        return None


with st.spinner("加载登记的数据版本…"):
    snapshots = request("/snapshots", params={"limit": 200})
if snapshots is None:
    st.stop()
available = [item for item in snapshots if item["source"] == "cex"]
if not available:
    st.warning(
        "暂无 CEX 数据版本。请按启动说明准备固定样本，再刷新。 / No CEX snapshots available."
    )
    st.code(
        "uv run python -m sentinel.cli seed\nuv run python -m sentinel.cli scenario missing",
        language="powershell",
    )
    st.stop()
# Prefer the deliberate missing case on first load; never encode fixture quantities.
available.sort(key=lambda item: (item.get("transform") != "missing", item["created_at"]))
with st.sidebar:
    st.subheader("核验范围 / Scope")
    selected = st.selectbox(
        "数据版本 / Version",
        available,
        format_func=lambda item: (
            f"{ {'missing': '缺失演练', 'stale': '延迟演练', None: '原始完整输入'}.get(item.get('transform'), item.get('transform')) } · {item['snapshot_id']}"
        ),
    )
    sid = selected["snapshot_id"]
    start = st.text_input("开始时间 · UTC（含）", selected["start"], key=f"start-{sid}")
    end = st.text_input("结束时间 · UTC（不含）", selected["end"], key=f"end-{sid}")
    st.caption(
        "窗口为 [开始, 结束)。来源：Binance ETHUSDT / 1m。ETH 数量与 USDT 计价数量分别展示。"
    )
    if st.button("刷新版本 / Refresh"):
        st.rerun()
    st.caption("更多来源、运行记录和可选模型见高级工程入口。")

question = st.text_area(
    "用户问题 / Question",
    "这张行情图的成交数量能否作为完整时间窗口的数字引用？请检查完整性并提供依据。",
    max_chars=2000,
    key="business-question",
)
params = {"source": "cex", "snapshot_id": sid, "start": start, "end": end}
try:
    if len(question.strip()) < 3:
        raise ValueError("问题至少需要三个字符")
    key = scope_key(params, question)
except ValueError as exc:
    st.error(
        "无效问题或时间窗：请填写有效问题和带时区的时间，结束晚于开始，最长七天，并按整分钟对齐。旧报告和导出已停用。"
    )
    with st.expander("输入校验详情 / Validation details"):
        st.text(str(exc)[:1000])
    st.stop()

state = st.session_state.setdefault("business", {})
if state.get("scope_key") and state["scope_key"] != key:
    st.warning("查询条件已改变：旧报告和导出已失效，请重新检查。 / Scope changed; run a new check.")
    state.clear()
if st.button("1. 检查数据 / Run checks", type="primary"):
    state.clear()
    with st.spinner("检查数据并核验登记证据…"):
        result = request(
            "/investigations",
            body={
                "context": params,
                "question": question,
                "mode": "deterministic",
                "baseline": "A",
            },
        )
        bundle = request(f"/investigations/{result['run_id']}/communication") if result else None
    if bundle:
        state.update(scope_key=key, bundle=bundle)

bundle = current_bundle(state, key)
if not bundle:
    st.write("先运行检查，再查看证据、恢复对照和双语交付物。未执行检查时不作正常判断。")
    st.caption("流程：检查数据 → 查看证据 → 从原始输入恢复 → 对照版本 → 用户说明与导出。")
    st.stop()

report = bundle["report"]
status = report["diagnosis"]
if status == "observed_data_issue":
    st.warning("⚠ " + bundle["judgment_zh"])
elif status == "insufficient_evidence":
    st.error("？ " + bundle["judgment_zh"])
else:
    st.info("✓ " + bundle["judgment_zh"])
st.caption(bundle["judgment_en"])
st.caption(data_notice(bundle["provenance"]))
st.caption(
    f"报告 {bundle['run_id']} · 固定历史版本 {report['snapshot_id']} · 生成于 {bundle['created_at']}"
)
lookup = {item["name"]: item for item in bundle["metrics"]}


def amount(name):
    item = lookup.get(name)
    return item["value"] if item else "未知"


columns = st.columns(3)
columns[0].metric(
    "覆盖记录 / Coverage", f"{amount('coverage_observed')} / {amount('coverage_expected')}"
)
columns[1].metric("缺失分钟 / Missing minutes", amount("coverage_missing"))
volume = lookup.get("base_volume")
columns[2].metric(
    "成交数量 / Base quantity",
    f"{Decimal(volume['value']):,.4f} {volume['unit']}" if volume else "未知",
    help=f"精确原值：{volume['value']} {volume['unit']}" if volume else "未取得指标",
)
st.write(
    "**下一步：** 查看关键证据；发现缺口时从登记的原始输入恢复，完成同窗口对照；引用前人工校审。"
)

if entry == "数据核验 / Engineering":
    st.subheader("2. 查看依据 / Evidence")
    st.write(f"UTC 时间窗：[{bundle['context']['start']}, {bundle['context']['end']})")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "指标": LABELS.get(m["name"], (m["name"],))[0],
                    "精确原值": m["value"],
                    "单位": m["unit"],
                    "证据引用": ", ".join(m["evidence_ids"]),
                }
                for m in bundle["metrics"]
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    findings = [e for e in bundle["evidence"] if e["kind"] == "quality_finding"]
    rule_names = {
        "missing_candles": "分钟记录缺失",
        "stale_data": "窗口尾部延迟",
        "invalid_rows": "无效记录",
        "conflicting_records": "同一标识记录冲突",
        "window_outside_snapshot": "查询超出登记范围",
    }
    for finding in findings:
        st.write(
            f"**{rule_names.get(finding['rule'], finding['rule'])}** · {finding['severity']} · 证据 `{finding['id']}`"
        )
        actual = finding["actual"]
        if finding["rule"] == "missing_candles":
            st.write(f"缺少 {actual.get('missing', '未知')} 个分钟观测。缺失时间（UTC）：")
            for missing_time in actual.get("items", []):
                st.write(missing_time)
        else:
            st.caption("请展开工程详情查看该检查项的登记证据。")
    origin = bundle["provenance"].get("provenance") or {}
    if origin.get("url"):
        st.link_button("公开历史原始来源 / Original source", origin["url"])
    st.caption(f"输入 checksum：{bundle['provenance'].get('input_checksum') or '未知'}")
    if st.button("查看登记原始样本 / Raw samples"):
        state["raw"] = request("/raw-samples", params=params)
    if state.get("raw"):
        for raw in state["raw"]:
            st.caption("原始输入的前三行，不代表缺失版本仍保留这些记录；缺失没有补零。")
            st.dataframe(pd.DataFrame(raw["sample"]), hide_index=True, width="stretch")
            with st.expander("原始 manifest 与校验值 / Technical provenance"):
                st.json(raw)
    rows = request("/chart", params=params)
    if rows:
        frame = pd.DataFrame(rows)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame["base_volume"] = pd.to_numeric(frame["base_volume"])
        x = alt.X(
            "timestamp:T", scale=alt.Scale(type="utc"), axis=alt.Axis(title="UTC", format="%H:%M")
        )
        chart = (
            alt.Chart(frame)
            .mark_bar(color="#0f766e")
            .encode(
                x=x, y=alt.Y("base_volume:Q", title="ETH"), tooltip=["timestamp:T", "base_volume:Q"]
            )
        )
        gap_times = [
            time
            for item in findings
            if item["rule"] == "missing_candles"
            for time in item["actual"].get("items", [])
        ]
        if gap_times:
            gaps = pd.DataFrame({"timestamp": pd.to_datetime(gap_times, utc=True)})
            chart += alt.Chart(gaps).mark_rule(color="#b91c1c", strokeDash=[4, 3]).encode(x=x)
        st.altair_chart(chart.properties(height=230), width="stretch")
        st.caption(
            "虚线标记缺失分钟；缺失观测没有补零。 / Dashed markers indicate missing observations, not zero volume."
        )
    elif rows == []:
        st.warning("窗口内没有图表记录；空图不代表零成交，判断以报告证据为准。")

    st.subheader("3. 从原始输入恢复 / Restore")
    st.write("重放登记的原始输入，保留当前故障版本和报告。恢复可能返回已存在的原始版本。")
    if st.button("从原始输入恢复 / Restore raw input"):
        with st.spinner("重放原始输入并检查同一窗口…"):
            receipt = request("/recoveries", body={"before_run_id": bundle["run_id"]})
            refreshed = (
                request(
                    f"/investigations/{bundle['run_id']}/communication",
                    params={"recovery_id": receipt["id"]},
                )
                if receipt
                else None
            )
        if refreshed:
            state["bundle"] = refreshed
            st.rerun()
        else:
            st.error("恢复结果不可用，未宣称恢复成功；原报告仍固定为历史版本。")

if bundle.get("recovery"):
    rec = bundle["recovery"]
    st.subheader("同一窗口 · 版本对照 / Same-window comparison")
    st.write(
        f"实际重放：{execution_label(rec['restore_status'])} · 恢复后核验：{execution_label(rec['verification_status'])}"
    )
    if rec["error"]:
        st.error(rec["error"])
    comparison_rows = []
    for version in bundle["comparison"]["versions"]:
        values = {m["name"]: m["value"] for m in version["report"]["metrics"]}
        comparison_rows.append(
            {
                "阶段": "恢复前" if version["role"] == "before" else "恢复后",
                "版本": version["report"]["snapshot_id"],
                "覆盖": f"{values.get('coverage_observed', '未知')}/{values.get('coverage_expected', '未知')}",
                "缺失": values.get("coverage_missing", "未知"),
                "ETH 精确原值": values.get("base_volume", "未知"),
                "判断": execution_label(version["report"]["diagnosis"]),
            }
        )
    st.dataframe(pd.DataFrame(comparison_rows), hide_index=True, width="stretch")
    st.warning(
        "这是同一时间窗的数据版本差异，不能写成市场涨跌。重放成功与通过核验是两个状态；通过已实现检查也不代表排除全部错误。"
    )

if entry == "用户说明 / Product & Content":
    st.subheader("4. 双语用户说明 / Communication draft")
    st.caption(
        "确定性模板 · 与上方指标共用事实 · 待人工校审 / Deterministic templates, shared facts, review pending"
    )
    zh, en, issue, faq = st.tabs(["中文说明", "English summary", "问题单 / Issue", "FAQ"])
    with zh:
        st.markdown(bundle["markdown_zh"])
    with en:
        st.markdown(bundle["markdown_en"])
    with issue:
        st.markdown(bundle["issue_markdown"])
    with faq:
        path = Path(__file__).resolve().parents[1] / "docs/workbench/faq.md"
        if path.exists():
            # Repository-relative footer links are for the checked-out docs, not HTTP routes.
            st.markdown(path.read_text(encoding="utf8").rsplit("\n[完整案例]", 1)[0])
        else:
            st.info("FAQ 文档尚未准备。")

st.subheader("5. 导出交付物 / Downloads")
st.caption("草稿待人工校审。导出固定为当前报告及关联恢复记录，不自动跟随其他数据版本。")
st.download_button(
    "下载双语业务说明 / Bilingual Markdown",
    bundle["markdown_zh"] + "\n---\n\n" + bundle["markdown_en"],
    file_name=f"communication-{bundle['run_id']}.md",
    mime="text/markdown",
)
st.download_button(
    "下载问题单 / Issue Markdown",
    bundle["issue_markdown"],
    file_name=f"issue-{bundle['run_id']}.md",
    mime="text/markdown",
)
st.download_button(
    "下载结构化证据 / Evidence JSON",
    json.dumps(bundle, ensure_ascii=False, indent=2),
    file_name=f"evidence-{bundle['run_id']}.json",
    mime="application/json",
)
with st.expander("工程详情 / Validated report and evidence"):
    st.json(bundle)
