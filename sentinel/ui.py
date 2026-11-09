"""Streamlit UI uses the HTTP API, including its validation and bounded model timeouts."""

import json
import os
from decimal import Decimal

import altair as alt
import httpx
import pandas as pd
import streamlit as st

API = os.getenv("SENTINEL_API_URL", "http://127.0.0.1:8000").rstrip("/")
st.set_page_config(page_title="MarketData Sentinel", page_icon="◈", layout="wide")
st.markdown(
    """<style>
    .block-container {padding-top:2rem;max-width:1400px}
    [data-testid="stMetric"] {background:#f1f5f9;border-radius:10px;padding:16px}
    [data-testid="stMetricValue"] {font-size:clamp(1rem,2vw,1.65rem)}
    </style>""",
    unsafe_allow_html=True,
)
st.title("◈ MarketData Sentinel")
st.caption("WEB3 DATA QUALITY WORKBENCH · UTC · EVIDENCE FIRST")
st.caption("Rule diagnosis + model evidence organization")


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
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"API request failed: {str(exc)[:350]}")
        return None


snapshots = request("/snapshots", params={"limit": 200})
if not snapshots:
    st.info("No snapshots available. Run `uv run python -m sentinel.cli seed` after migrations.")
    st.stop()

with st.sidebar:
    st.subheader("Investigation scope")
    source = st.selectbox(
        "Source",
        ["cex", "dex"],
        format_func=lambda s: {
            "cex": "Binance · ETH/USDT · 1 minute",
            "dex": "Ethereum · Uniswap v3 · USDC/WETH",
        }[s],
    )
    available = [s for s in snapshots if s.get("source") == source]
    scene = st.selectbox(
        "Demo view",
        ["all", "normal", "missing", "stale"],
        format_func=lambda v: {
            "all": "All versions",
            "normal": "Normal data",
            "missing": "Missing data",
            "stale": "Stale data",
        }[v],
    )
    if scene != "all":
        available = [s for s in available if (s.get("transform") or "normal") == scene]
    if not available:
        st.info(
            f"No matching version. Run: uv run python -m sentinel.cli scenario {scene if scene != 'all' else 'normal'}"
        )
        st.stop()
    selected = st.selectbox(
        "Pinned data version",
        available,
        format_func=lambda s: (
            f"{s.get('transform') or 'normal'} · {s.get('snapshot_id', s.get('id', 'Unknown'))}"
        ),
    )
    sid = selected.get("snapshot_id", selected.get("id"))
    start = st.text_input(
        "Start · UTC inclusive", selected.get("start", selected.get("event_start", ""))
    )
    end = st.text_input(
        "End · UTC exclusive", selected.get("end", selected.get("expected_end", ""))
    )
    st.caption("Half-open window [start, end). Reports stay pinned to this version.")
    st.divider()
    st.markdown("**Repeatable fault demo**")
    st.code("uv run python -m sentinel.cli scenario missing", language="powershell")
    st.caption("Refresh versions after creating a scenario. Restore uses registered raw data.")
    if st.button("Refresh versions"):
        st.rerun()

params = {"source": source, "snapshot_id": sid, "start": start, "end": end}
overview, investigate_tab, data_tab = st.tabs(["Overview", "Investigate", "Data & Runs"])

with overview:
    st.subheader("Is the observed change supported by complete data?")
    data_label = (
        "Synthetic demonstration data"
        if selected.get("synthetic", True)
        else "Public historical data"
    )
    st.info(
        f"{selected.get('mode', 'snapshot replay')} · {data_label} · Model: deterministic by default."
    )
    st.caption(f"PINNED VERSION  {sid}")
    metrics = request("/metrics", params=params)
    quality = request("/quality", params=params)
    ingestion = request("/ingestion", params=params)
    if metrics:
        cols = st.columns(3)
        cols[0].metric(
            "K-line rows" if source == "cex" else "Swap events", metrics.get("row_count", "—")
        )
        volume_key = "base_volume" if source == "cex" else "token0_volume"
        cols[1].metric(
            "Base volume · ETH" if source == "cex" else "Single-side volume · USDC",
            f"{Decimal(metrics[volume_key]):,.2f}" if volume_key in metrics else "—",
            help=f"Exact value: {metrics.get(volume_key, 'unknown')}. Display rounded to two decimals only.",
        )
        cols[2].metric(
            "Trade count" if source == "cex" else "Source",
            (
                metrics.get("number_of_trades")
                if metrics.get("number_of_trades") is not None
                else "Unknown"
            )
            if source == "cex"
            else "Ethereum / 1 pool",
        )
        with st.expander("Exact metrics and comparison windows"):
            st.json(metrics)
        rows = request("/chart", params=params)
        if rows:
            frame = pd.DataFrame(rows)
            time_key = next(
                (k for k in ("open_time", "event_time", "timestamp", "time") if k in frame.columns),
                None,
            )
            value_key = next(
                (
                    k
                    for k in ("base_volume", "token0_volume", "token0_amount", "volume")
                    if k in frame.columns
                ),
                None,
            )
            if time_key and value_key:
                frame[time_key] = pd.to_datetime(frame[time_key], utc=True)
                frame[value_key] = pd.to_numeric(frame[value_key])
                frame["timestamp_utc"] = frame[time_key].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                x = alt.X(
                    f"{time_key}:T",
                    scale=alt.Scale(type="utc"),
                    axis=alt.Axis(title="Event time · UTC", format="%H:%M"),
                )
                volume_chart = (
                    alt.Chart(frame)
                    .mark_bar(color="#0f766e")
                    .encode(
                        x=x,
                        y=alt.Y(
                            f"{value_key}:Q",
                            title="Volume · ETH" if source == "cex" else "Token0 amount · USDC",
                        ),
                        tooltip=[
                            alt.Tooltip("timestamp_utc:N", title="UTC"),
                            alt.Tooltip(f"{value_key}:Q"),
                        ],
                    )
                )
                missing = metrics.get("coverage", {}).get("missing_items", [])
                if source == "cex" and missing:
                    gap_frame = pd.DataFrame({time_key: pd.to_datetime(missing, utc=True)})
                    markers = (
                        alt.Chart(gap_frame)
                        .mark_rule(color="#dc2626", strokeDash=[3, 3])
                        .encode(x=x)
                    )
                    volume_chart = volume_chart + markers
                    st.caption(
                        "Red dashed markers: missing expected minutes. No zero volume was invented for these gaps."
                    )
                st.altair_chart(volume_chart.properties(height=240), width="stretch")
            if "close" in frame.columns and time_key:
                frame["close"] = pd.to_numeric(frame["close"])
                price_chart = (
                    alt.Chart(frame)
                    .mark_line(color="#334155")
                    .encode(
                        x=x,
                        y=alt.Y(
                            "close:Q", scale=alt.Scale(zero=False), title="Close · USDT per ETH"
                        ),
                        tooltip=["timestamp_utc:N", "close:Q"],
                    )
                )
                st.altair_chart(price_chart.properties(height=170), width="stretch")
    if quality:
        st.markdown("**Quality checks and evidence**")
        findings = quality.get("findings", []) if isinstance(quality, dict) else quality
        if findings:
            st.warning("Review the findings before interpreting volume changes.")
            st.dataframe(pd.DataFrame(findings), width="stretch", hide_index=True)
        else:
            st.success(
                "No issue found in executed checks. This does not prove absolute correctness."
            )
    if ingestion:
        coverage = ingestion.get("coverage", {})
        lag = ingestion.get("lag_seconds")
        st.caption(
            f"Coverage: {coverage.get('observed', '—')}/{coverage.get('expected', '—')} {coverage.get('unit', '')} · Reference lag: {str(lag) + ' seconds' if lag is not None else 'unknown'} · Last successful import: {ingestion.get('last_success_at') or 'None'}"
        )
        with st.expander("Coverage, checkpoint, and last successful collection"):
            st.json(ingestion)

with investigate_tab:
    st.subheader("Investigate a change")
    st.caption("Only registered evidence and four bounded read-only tools are available.")
    question = st.text_area(
        "Question",
        "Did volume decline because of missing or delayed data? Check coverage and show supporting evidence.",
        max_chars=2000,
    )
    model_mode = st.selectbox("Model mode", ["deterministic", "live_llm"])
    baseline = (
        "A"
        if model_mode == "deterministic"
        else st.selectbox(
            "Live approach",
            ["C", "B"],
            format_func=lambda b: {"B": "B · One-shot LLM", "C": "C · Tool-calling investigation"}[
                b
            ],
        )
    )
    if model_mode == "live_llm":
        st.caption(
            "Requires configured provider, model, key and base URL. Failures produce a labeled deterministic fallback."
        )
    scope_key = json.dumps([params, question, model_mode, baseline], sort_keys=True)
    if st.button("Run investigation", type="primary"):
        with st.spinner("Checking the pinned snapshot and validating evidence…"):
            result = request(
                "/investigations",
                body={
                    "context": params,
                    "question": question,
                    "mode": model_mode,
                    "baseline": baseline,
                },
            )
        if result:
            st.session_state.setdefault("reports", {})[scope_key] = result
    result = st.session_state.get("reports", {}).get(scope_key)
    if result:
        report = result["report"]
        st.subheader(report["diagnosis"].replace("_", " ").capitalize())
        st.caption(
            f"Actual mode: {result.get('actual_model_mode', result['model_mode'])} · Status: {result['execution_status']} · Cost: {result.get('cost_usd') or 'unknown'}"
        )
        if result.get("failure"):
            st.warning(result["failure"]["message"])
        st.caption(
            "Numbers below are rounded for reading; the validated JSON retains exact metric values and references."
        )
        metric_lookup = {m["id"]: m for m in report["metrics"]}
        for fact in report["facts"]:
            statement = fact["statement"]
            for metric_id in fact.get("metric_refs", []):
                metric = metric_lookup[metric_id]
                statement = statement.replace(
                    metric["value"],
                    f"{Decimal(metric['value']):,.4f}".rstrip("0").rstrip(".")
                    if "." in metric["value"]
                    else f"{Decimal(metric['value']):,.0f}",
                )
            st.markdown(f"- {statement}")
        st.markdown("**Next checks**")
        for recommendation in report["recommendations"]:
            st.write(recommendation)
        with st.expander("Limitations"):
            for limitation in report["limitations"]:
                st.write(limitation)
        with st.expander("Tool calls and timing"):
            st.dataframe(pd.DataFrame(result["trace"]), width="stretch", hide_index=True)
        if st.button("Open report evidence"):
            evidence = request(
                "/evidence",
                params=[("snapshot_id", sid)] + [("ids", v) for v in report["evidence_refs"][:30]],
            )
            if evidence:
                st.json(evidence)
        with st.expander("Validated report JSON"):
            st.json(result, expanded=1)
        st.download_button(
            "Download report JSON",
            data=json.dumps(result, indent=2),
            file_name="investigation.json",
            mime="application/json",
        )

with data_tab:
    st.subheader("Reproducible data and runs")
    st.caption("Raw samples and hashes are accessible through registered evidence only.")
    st.dataframe(pd.DataFrame(snapshots), width="stretch", hide_index=True)
    runs = request("/runs", params={"limit": 50})
    if runs:
        st.dataframe(pd.DataFrame(runs), width="stretch", hide_index=True)
    if st.button("Open registered raw samples"):
        raw = request("/raw-samples", params=params)
        if raw:
            st.json(raw)
    evidence_ids = st.text_input(
        "Evidence IDs · comma separated", placeholder="Paste an ID from a finding or report"
    )
    if st.button("Open evidence"):
        ids = [v.strip() for v in evidence_ids.split(",") if v.strip()]
        if ids:
            evidence = request(
                "/evidence", params=[("snapshot_id", sid)] + [("ids", v) for v in ids]
            )
            if evidence:
                st.json(evidence)
        else:
            st.info("Enter a registered evidence ID.")
