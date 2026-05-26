"""Orders360 data product overview — KPI dashboard over the Vulcan API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

DEFAULT_BASE_URL = (
    "https://pacific-051426.dataos.cloud/product-sandbox/vulcan/orders360-vdetrue"
)

PHYSICAL_KINDS = {
    "SEED",
    "FULL",
    "INCREMENTAL",
    "INCREMENTAL_BY_TIME_RANGE",
    "VIEW",
    "EXTERNAL",
    "EMBEDDED",
}


st.set_page_config(
    page_title="Orders360 Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
.hero {
    padding: 1.25rem 1.5rem;
    border-radius: 12px;
    background: linear-gradient(120deg, #0f172a 0%, #1e3a5f 55%, #0f766e 100%);
    color: #f8fafc;
    margin-bottom: 1.25rem;
}
.hero h1 { color: #fff; font-size: 1.75rem; margin: 0 0 0.35rem 0; }
.hero p { color: #cbd5e1; margin: 0; font-size: 0.95rem; }
.kpi {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    min-height: 108px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.kpi-label { font-size: 0.82rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; }
.kpi-value { font-size: 2rem; font-weight: 800; color: #0f172a; line-height: 1.1; margin: 0.2rem 0; }
.kpi-note { font-size: 0.82rem; color: #94a3b8; }
.badge-ok { color: #166534; background: #dcfce7; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; }
.badge-warn { color: #854d0e; background: #fef9c3; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; }
.badge-bad { color: #991b1b; background: #fee2e2; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.75rem; font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)


def get_config(key: str, default: str = "") -> str:
    env_key = key.upper()
    if os.environ.get(env_key):
        return os.environ[env_key]
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def normalize_base(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url.endswith("/api/v1"):
        url = url[: -len("/api/v1")]
    return url


def api_get(base_url: str, token: str, path: str, params: Optional[Dict] = None) -> Tuple[Any, Optional[str]]:
    url = f"{normalize_base(base_url)}{path}"
    headers = {"Accept": "application/json"}
    if token.strip():
        headers["Authorization"] = f"Bearer {token.strip()}"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=45)
        if resp.status_code >= 400:
            return None, f"HTTP {resp.status_code}: {resp.text[:300]}"
        return resp.json(), None
    except Exception as exc:
        return None, str(exc)


def safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def item_name(item: Any) -> str:
    """Extract a display name from API values that may be str or dict."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(
            item.get("name")
            or item.get("fqn")
            or item.get("model")
            or item.get("model_name")
            or "—"
        )
    if item is None:
        return "—"
    return str(item)


def join_items(items: List[Any], limit: int = 5) -> str:
    names = [item_name(x) for x in items if x is not None]
    if not names:
        return "—"
    shown = names[:limit]
    extra = len(names) - limit
    suffix = f" (+{extra} more)" if extra > 0 else ""
    return ", ".join(shown) + suffix


def lineage_df(graph: Any) -> pd.DataFrame:
    """Build lineage table from graph (nodes/edges) or legacy model -> deps map."""
    if not graph:
        return pd.DataFrame()

    if isinstance(graph, dict) and "nodes" in graph:
        rows = []
        for node in safe_list(graph.get("nodes")):
            if not isinstance(node, dict):
                continue
            rows.append(
                {
                    "Model": node.get("name", "—"),
                    "Kind": node.get("kind", "—"),
                    "Parents": join_items(safe_list(node.get("parents"))),
                    "Children": join_items(safe_list(node.get("children"))),
                }
            )
        return pd.DataFrame(rows)

    if isinstance(graph, dict):
        rows = []
        for model, deps in graph.items():
            if model in ("nodes", "edges"):
                continue
            rows.append({"Model": model, "Depends on": join_items(safe_list(deps))})
        return pd.DataFrame(rows)

    return pd.DataFrame()


def lineage_edges_df(graph: Any) -> pd.DataFrame:
    if not isinstance(graph, dict):
        return pd.DataFrame()
    rows = [
        {"From": item_name(e.get("from")), "To": item_name(e.get("to"))}
        for e in safe_list(graph.get("edges"))
        if isinstance(e, dict)
    ]
    return pd.DataFrame(rows)


def ts_label(value: Any) -> str:
    if value in (None, "", "N/A"):
        return "—"
    try:
        ts = int(value)
        if ts > 1_000_000_000_000:
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return str(value)


def kpi_card(label: str, value: Any, note: str = "") -> None:
    st.markdown(
        f"""
<div class="kpi">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  <div class="kpi-note">{note}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def count_physical_models(metadata: Dict[str, Any]) -> int:
    count = 0
    for model in safe_list(metadata.get("models")):
        kind = str(model.get("kind", "")).upper()
        if kind in PHYSICAL_KINDS:
            count += 1
    return count


def physical_models_df(metadata: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for model in safe_list(metadata.get("models")):
        kind = str(model.get("kind", "")).upper()
        if kind not in PHYSICAL_KINDS:
            continue
        rows.append(
            {
                "Model": model.get("name", "—"),
                "Kind": kind,
                "Schedule": model.get("cron", "—"),
                "Columns": len(safe_list(model.get("columns"))),
                "Description": (model.get("description") or "—")[:120],
            }
        )
    return pd.DataFrame(rows)


def semantic_df(semantic: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for model in safe_list(semantic.get("models")):
        kind = str(model.get("kind", "")).upper()
        dims = [c.get("name") for c in safe_list(model.get("columns")) if c.get("kind") == "dimension"]
        meas = [c.get("name") for c in safe_list(model.get("columns")) if c.get("kind") == "measure"]
        rows.append(
            {
                "Name": model.get("name", "—"),
                "Type": kind,
                "Dimensions": ", ".join(dims[:6]) or "—",
                "Measures": ", ".join(meas[:6]) or "—",
            }
        )
    return pd.DataFrame(rows)


def freshness_df(metadata: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in safe_list(metadata.get("status")):
        pending = bool(item.get("is_pending"))
        rows.append(
            {
                "Model": item.get("model", "—"),
                "Last run": item.get("most_recent_run", "—"),
                "Next expected": item.get("nominal_next", "—"),
                "Status": "Pending" if pending else "Fresh",
            }
        )
    return pd.DataFrame(rows)


def quality_summary_df(quality: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    summary = quality.get("summary", {}) if isinstance(quality, dict) else {}
    dims = quality.get("dimensions", {}) if isinstance(quality, dict) else {}
    for dim, stats in dims.items():
        rows.append(
            {
                "Dimension": str(dim).title(),
                "Total": stats.get("total", 0),
                "Pass": stats.get("pass", 0),
                "Fail": stats.get("fail", 0),
                "Pass rate %": stats.get("pass_rate", 0),
            }
        )
    if not rows and summary:
        rows.append(
            {
                "Dimension": "Overall",
                "Total": summary.get("total", 0),
                "Pass": summary.get("pass", 0),
                "Fail": summary.get("fail", 0),
                "Pass rate %": summary.get("pass_rate", 0),
            }
        )
    return pd.DataFrame(rows)


def checks_df(checks: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for check in safe_list(checks.get("checks")):
        runs = safe_list(check.get("runs"))
        outcome = runs[0].get("outcome", "—") if runs else check.get("latest_outcome", "—")
        rows.append(
            {
                "Check": check.get("check_name", "—"),
                "Model": check.get("model_name", "—"),
                "Dimension": str(check.get("dimension", "—")).title(),
                "Outcome": str(outcome).title(),
            }
        )
    return pd.DataFrame(rows)


def plans_df(plans: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for plan in safe_list(plans.get("plans")):
        changes = plan.get("changes", {}) if isinstance(plan.get("changes"), dict) else {}
        direct = safe_list(changes.get("direct")) or safe_list(plan.get("directly_modified"))
        indirect = safe_list(changes.get("indirect")) or safe_list(plan.get("indirectly_modified"))
        added = safe_list(changes.get("added"))
        rows.append(
            {
                "Plan ID": (plan.get("plan_id") or "—")[:12] + "…",
                "Started": ts_label(plan.get("start_ts")),
                "Success": "Yes" if plan.get("success", True) else "No",
                "Direct": len(direct),
                "Indirect": len(indirect),
                "Added": len(added),
                "Commit": (plan.get("git_commit_sha") or "—")[:8],
            }
        )
    return pd.DataFrame(rows)


def runs_df(runs_payload: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for run in safe_list(runs_payload.get("runs")):
        models = safe_list(run.get("models_affected"))
        ok = all(m.get("rows_affected", 0) is not None for m in models) if models else True
        rows.append(
            {
                "Run ID": (run.get("run_id") or "—")[:12] + "…",
                "Plan": (run.get("plan_id") or "—")[:12] + "…",
                "Started": ts_label(run.get("start_ts")),
                "Models": len(models),
                "Duration": f"{(int(run.get('end_ts', 0)) - int(run.get('start_ts', 0))) // 1000}s"
                if run.get("end_ts") and run.get("start_ts")
                else "—",
                "Status": "OK" if ok else "Review",
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=120, show_spinner=False)
def load_dashboard_data(base_url: str, token: str) -> Dict[str, Any]:
    endpoints = {
        "metadata": "/api/v1/metadata",
        "semantic": "/api/v1/metadata/semantic",
        "quality": "/api/v1/quality",
        "checks": "/api/v1/quality/checks",
        "plans": "/api/v1/activity/plans",
        "runs": "/api/v1/activity/runs",
        "models_latest": "/api/v1/activity/models",
        "usage": "/api/v1/query/usage-metrics",
    }
    params = {
        "checks": {"limit": 50, "offset": 0},
        "plans": {"limit": 10, "offset": 0},
        "runs": {"limit": 10, "offset": 0},
    }
    data: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    for key, path in endpoints.items():
        body, err = api_get(base_url, token, path, params.get(key))
        data[key] = body or {}
        if err:
            errors[key] = err
    return {"data": data, "errors": errors}


# --- Header ---
base_url = get_config("VULCAN_BASE_URL", DEFAULT_BASE_URL)
token = get_config("VULCAN_AUTH_TOKEN", "")

with st.sidebar:
    st.header("Connection")
    base_url = st.text_input("Data product URL", value=base_url)
    token = st.text_input("API token", value=token, type="password")
    if st.button("Refresh data", type="primary", use_container_width=True):
        load_dashboard_data.clear()

if not token:
    st.warning("Add your DataOS API token in the sidebar (or set `VULCAN_AUTH_TOKEN`).")

payload = load_dashboard_data(base_url, token)
data = payload["data"]
errors = payload["errors"]

metadata = data.get("metadata", {})
semantic = data.get("semantic", {})
quality = data.get("quality", {})
checks = data.get("checks", {})
plans = data.get("plans", {})
runs = data.get("runs", {})
usage = data.get("usage", {})

product = metadata.get("product", {}) if isinstance(metadata, dict) else {}
display_name = product.get("display_name") or metadata.get("name", "Data Product")
domain = product.get("domain", "—")
gateway = metadata.get("gateway", {}) if isinstance(metadata, dict) else {}

sdf = semantic_df(semantic)
physical_count = count_physical_models(metadata)
semantic_count = int((sdf["Type"] == "SEMANTIC").sum()) if not sdf.empty else 0
metric_count = int((sdf["Type"] == "METRIC").sum()) if not sdf.empty else 0

q_summary = quality.get("summary", {}) if isinstance(quality, dict) else {}
quality_total = q_summary.get("total") or quality.get("checks_count", 0)
quality_pass_rate = q_summary.get("pass_rate", 0)

plans_total = plans.get("total") if isinstance(plans, dict) else len(safe_list(plans.get("plans")))
runs_total = len(safe_list(runs.get("runs")))
queries_total = usage.get("queries", usage.get("total_queries", 0))
active_users = usage.get("active_users", 0)

st.markdown(
    f"""
<div class="hero">
  <h1>{display_name}</h1>
  <p>Live overview from the Vulcan API — models, semantics, quality, activity, and query usage.</p>
</div>
""",
    unsafe_allow_html=True,
)

if errors:
    with st.expander("API warnings", expanded=False):
        for name, msg in errors.items():
            st.caption(f"**{name}**: {msg}")

# --- KPI row ---
c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
with c1:
    kpi_card("Physical models", physical_count, "SEED, FULL, incremental")
with c2:
    kpi_card("Semantic models", semantic_count, "Consumption layer")
with c3:
    kpi_card("Metrics", metric_count, "Business metrics")
with c4:
    kpi_card("Quality checks", quality_total, f"{quality_pass_rate}% pass rate")
with c5:
    kpi_card("Plans", plans_total or len(safe_list(plans.get("plans"))), "Deployments")
with c6:
    kpi_card("Runs", runs_total, "Recent executions")
with c7:
    kpi_card("Queries", queries_total, "This period")
with c8:
    kpi_card("Active users", active_users, "Consumers")

st.caption(
    f"Domain: **{domain}** · Gateway: **{gateway.get('connection_type', '—')}** "
    f"({gateway.get('dialect', '—')}) · Tenant: **{metadata.get('tenant', '—')}**"
)

overview_tab, models_tab, semantic_tab, quality_tab, activity_tab, usage_tab = st.tabs(
    ["Overview", "Physical models", "Semantic layer", "Quality", "Runs & plans", "Query usage"]
)

with overview_tab:
    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("Product summary")
        st.write(product.get("description", "No description returned."))
        tags = safe_list(product.get("tags"))
        if tags:
            st.write(" ".join(f"`{t}`" for t in tags[:8]))
    with right:
        st.subheader("Freshness")
        fdf = freshness_df(metadata)
        if not fdf.empty:
            st.dataframe(fdf, use_container_width=True, hide_index=True)
        else:
            st.info("No freshness status in metadata.")

    st.subheader("Lineage")
    graph = metadata.get("graph", {}) if isinstance(metadata, dict) else {}
    ldf = lineage_df(graph)
    if not ldf.empty:
        st.dataframe(ldf, use_container_width=True, hide_index=True)
        edf = lineage_edges_df(graph)
        if not edf.empty:
            with st.expander("Lineage edges"):
                st.dataframe(edf, use_container_width=True, hide_index=True)
    else:
        st.caption("Lineage graph not populated in this response.")

with models_tab:
    pdf = physical_models_df(metadata)
    if pdf.empty:
        st.info("No physical models found.")
    else:
        st.dataframe(pdf, use_container_width=True, hide_index=True)

with semantic_tab:
    if sdf.empty:
        st.info("No semantic schema returned.")
    else:
        st.dataframe(sdf, use_container_width=True, hide_index=True)

with quality_tab:
    q1, q2 = st.columns(2)
    with q1:
        st.subheader("By dimension")
        qdf = quality_summary_df(quality)
        if not qdf.empty:
            st.dataframe(qdf, use_container_width=True, hide_index=True)
            st.bar_chart(qdf.set_index("Dimension")[["Pass rate %"]])
        else:
            st.info("No quality summary.")
    with q2:
        st.subheader("Individual checks")
        cdf = checks_df(checks)
        if cdf.empty:
            st.info("No check details.")
        else:
            st.dataframe(cdf, use_container_width=True, hide_index=True)

with activity_tab:
    st.subheader("Recent plans")
    pdf_plans = plans_df(plans)
    if pdf_plans.empty:
        st.info("No deployment plans.")
    else:
        st.dataframe(pdf_plans, use_container_width=True, hide_index=True)

    st.subheader("Recent runs")
    rdf = runs_df(runs)
    if rdf.empty:
        st.info("No run history.")
    else:
        st.dataframe(rdf, use_container_width=True, hide_index=True)

with usage_tab:
    u1, u2, u3, u4 = st.columns(4)
    with u1:
        kpi_card("Queries", queries_total, "Total volume")
    with u2:
        kpi_card("Active users", active_users, "This period")
    with u3:
        kpi_card("New users", usage.get("new_users", 0), "First-time")
    with u4:
        median = usage.get("median_query_time_ms", usage.get("median_execution_ms", "—"))
        kpi_card("Median latency", f"{median} ms" if median != "—" else "—", "Query performance")

    savings = usage.get("pct_savings")
    if savings is not None:
        st.caption(f"Compute savings from cache: **{round(float(savings) * 100, 1)}%**")

st.divider()
st.caption(
    "Endpoints: `/metadata`, `/metadata/semantic`, `/quality`, `/quality/checks`, "
    "`/activity/plans`, `/activity/runs`, `/query/usage-metrics`"
)
